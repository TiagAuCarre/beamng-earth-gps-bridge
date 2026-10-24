package earth.beamng.gpsbridge

import android.Manifest
import android.app.*
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothServerSocket
import android.bluetooth.BluetoothSocket
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.util.UUID
import kotlin.concurrent.thread
import kotlin.math.*

class BridgeService : Service() {
    @Volatile private var running = false
    private var peer: BluetoothSocket? = null
    private var serverSocket: BluetoothServerSocket? = null
    private var lastSeq = -1L
    private var lastStream = ""
    private var providerReady = false
    private var lastPosition: Location? = null
    private var staleWatcher: Thread? = null
    private val loc by lazy { getSystemService(LOCATION_SERVICE) as LocationManager }
    private val provider = LocationManager.GPS_PROVIDER
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() { super.onCreate(); activeInstance = this; createChannel(); promoteForeground() }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "STOP") { stopSelf(); return START_NOT_STICKY }
        enabled = intent?.getBooleanExtra("inject", enabled) ?: enabled
        promoteForeground()
        if (!running) { running = true; updateConnectionState("Service démarré"); thread(name = "rfcomm-server") { phoneServerLoop() }; staleWatcher = thread(name = "stale-watch") { staleLoop() } }
        return START_STICKY
    }

    private fun promoteForeground() {
        if (Build.VERSION.SDK_INT >= 29) {
            val connected = android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
            val location = if (enabled) android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION else 0
            startForeground(7, notification("Attente du connecteur Windows"), connected or location)
        } else startForeground(7, notification("Attente du connecteur Windows"))
    }

    private fun phoneServerLoop() {
        val adapter = BluetoothAdapter.getDefaultAdapter()
        while (running) {
            var listener: BluetoothServerSocket? = null
            var socket: BluetoothSocket? = null
            try {
                if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) throw SecurityException("BLUETOOTH_CONNECT non accordée")
                if (adapter == null || !adapter.isEnabled) throw IllegalStateException("Bluetooth désactivé ou indisponible")
                listener = adapter.listenUsingRfcommWithServiceRecord("BeamNG GPS Bridge", UUID.fromString(SPP_UUID))
                serverSocket = listener
                updateConnectionState("Service SPP prêt")
                socket = listener.accept()
                peer = socket; updateConnectionState("Connecteur Windows connecté"); updateNotification("Connecteur Windows connecté")
                readPositions(socket)
            } catch (e: Exception) {
                if (running) updateConnectionState("Erreur RFCOMM")
            } finally {
                try { socket?.close() } catch (_: Exception) {}
                if (peer === socket) peer = null
                try { listener?.close() } catch (_: Exception) {}
                if (serverSocket === listener) serverSocket = null
            }
            if (running && autoReconnect) {
                try { Thread.sleep(reconnectDelayMs) } catch (_: InterruptedException) {}
            } else break
        }
    }

    private fun readPositions(socket: BluetoothSocket) {
        val input = socket.inputStream
        while (running && socket.isConnected) {
            val line = readLineBounded(input) ?: break
            try { acceptPosition(JSONObject(line)) } catch (_: Exception) { updateConnectionState("Message refusé") }
        }
        updateConnectionState("RFCOMM déconnecté")
    }

    /** Read one UTF-8 JSONL record with a hard byte limit; BufferedReader.readLine can grow unbounded. */
    private fun readLineBounded(input: java.io.InputStream): String? {
        val bytes = ByteArrayOutputStream(256)
        while (true) {
            val next = input.read()
            if (next < 0) {
                if (bytes.size() == 0) return null
                throw IllegalArgumentException("ligne JSON tronquée sans retour à la ligne")
            }
            if (next == 10) return Charsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes.toByteArray())).toString().removeSuffix("\r")
            if (bytes.size() >= 4096) throw IllegalArgumentException("message > 4096 octets")
            bytes.write(next)
        }
    }

    @Synchronized private fun acceptPosition(o: JSONObject) {
        val fields = setOf("version", "type", "source", "stream_id", "seq", "timestamp_utc_ms", "latitude", "longitude", "altitude_m", "speed_mps", "heading_deg", "test")
        require(o.keys().asSequence().toSet() == fields) { "champs JSON absents ou inconnus" }
        require(o.getInt("version") == 1 && o.getString("type") == "position") { "version/type non pris en charge" }
        val source = o.getString("source"); require(source == "beamng-earth" || source == "test") { "source invalide" }
        require(o.getBoolean("test") == (source == "test")) { "marque test incohérente" }
        val seq = o.getLong("seq"); val stream = o.getString("stream_id")
        require(seq >= 0 && stream.isNotBlank() && stream.length <= 64) { "séquence/flux invalide" }
        require(seq > lastSeq || stream != lastStream) { "séquence répétée ou ancienne" }
        val timestamp = o.getLong("timestamp_utc_ms"); val age = System.currentTimeMillis() - timestamp
        require(age in -60_000..3_000) { "message périmé (${age} ms)" }
        val lat = o.getDouble("latitude"); val lon = o.getDouble("longitude"); val speed = o.getDouble("speed_mps")
        require(lat.isFinite() && lat in -90.0..90.0 && lon.isFinite() && lon in -180.0..180.0 && speed.isFinite() && speed in 0.0..150.0) { "coordonnées/vitesse invalides" }
        val altitude = if (o.isNull("altitude_m")) null else o.getDouble("altitude_m")
        val heading = if (o.isNull("heading_deg")) null else o.getDouble("heading_deg")
        require(altitude == null || (altitude.isFinite() && altitude in -12000.0..100000.0)) { "altitude invalide" }
        require(heading == null || (heading.isFinite() && heading in 0.0..360.0)) { "cap invalide" }
        lastSeq = seq; lastStream = stream
        // LocationManager requires an accuracy value; 50 m is a conservative placeholder because
        // BeamNG.earth does not report GNSS-like uncertainty. It is not a measured accuracy.
        val l = Location(provider).apply { latitude = lat; longitude = lon; time = timestamp; elapsedRealtimeNanos = SystemClock.elapsedRealtimeNanos(); accuracy = 50f; this.speed = speed.toFloat(); if (altitude != null) this.altitude = altitude; if (heading != null) { bearing = heading.toFloat().rem(360f); bearingAccuracyDegrees = 10f } }
        lastPosition = l
        latestPositionText = "${"%.6f".format(java.util.Locale.US, lat)}, ${"%.6f".format(java.util.Locale.US, lon)} • ${"%.1f".format(java.util.Locale.US, speed * 3.6)} km/h • cap ${if (o.isNull("heading_deg")) "inconnu" else "${o.getDouble("heading_deg")}°"}"
        lastPositionWallMs = System.currentTimeMillis()
        connectionState = "Connecté au PC appairé"
        if (enabled) inject(l)
    }

    private fun inject(l: Location): String {
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) return "injection indisponible : permission localisation manquante"
        return try {
            if (!providerReady) {
                if (!loc.isProviderEnabled(provider)) { /* test provider can still be registered when GPS is disabled */ }
                try { loc.addTestProvider(provider, false, false, false, false, true, true, true, 1, 1) } catch (_: IllegalArgumentException) { /* provider exists */ }
                loc.setTestProviderEnabled(provider, true); providerReady = true
            }
            loc.setTestProviderLocation(provider, l); "position injectée par API test"
        } catch (e: SecurityException) { "injection refusée : ${e.message}" } catch (e: Exception) { "injection impossible : ${e.message}" }
    }

    private fun staleLoop() { while (running) { Thread.sleep(750); val p = lastPosition; if (p != null && System.currentTimeMillis() - p.time > 3000) { if (providerReady) removeProvider(); lastPosition = null; updateConnectionState("Position périmée"); updateNotification("Position périmée • injection suspendue") } } }
    private fun removeProvider() { try { loc.setTestProviderEnabled(provider, false); loc.removeTestProvider(provider) } catch (_: Exception) {}; providerReady = false }

    override fun onDestroy() { running = false; try { peer?.close() } catch (_: Exception) {}; try { serverSocket?.close() } catch (_: Exception) {}; removeProvider(); activeInstance = null; connectionState = "Service arrêté"; super.onDestroy() }
    private fun createChannel() { if (Build.VERSION.SDK_INT >= 26) getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel(CHANNEL, "BeamNG GPS Bridge", NotificationManager.IMPORTANCE_LOW)) }
    private fun notification(text: String) = Notification.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.ic_menu_mylocation).setContentTitle("BeamNG GPS Bridge").setContentText(text).setOngoing(true).build()
    private fun updateNotification(text: String) { getSystemService(NotificationManager::class.java).notify(7, notification(text)) }

    companion object {
        const val SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"; private const val CHANNEL = "gps_bridge"
        @Volatile private var enabled = false
        @Volatile private var activeInstance: BridgeService? = null
        @Volatile private var autoReconnect = true
        @Volatile private var reconnectDelayMs = 1500L
        @Volatile var connectionState = "Arrêté"
        @Volatile var latestPositionText = "Aucune position"
        @Volatile var lastPositionWallMs = 0L
        fun setInjection(value: Boolean) {
            enabled = value
            activeInstance?.let { service ->
                if (!value) service.removeProvider()
                service.promoteForeground()
            }
        }
        fun setReconnectDelay(milliseconds: Long) { reconnectDelayMs = milliseconds.coerceIn(1000L, 30000L) }
        fun updateConnectionState(event: String) {
            connectionState = when (event) {
                "Service démarré", "Service SPP prêt" -> "En attente du connecteur Windows"
                "Connecteur Windows connecté" -> "Connecté au PC appairé"
                "RFCOMM déconnecté" -> "Bluetooth déconnecté"
                "Erreur RFCOMM" -> "Erreur de connexion Bluetooth"
                "Message refusé" -> "Message GPS invalide"
                "Position périmée" -> "Position périmée • injection suspendue"
                else -> connectionState
            }
        }
    }
}
