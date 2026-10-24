package earth.beamng.gpsbridge

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.content.ClipData
import android.content.ClipboardManager
import android.provider.Settings
import android.view.ViewGroup
import android.view.View
import android.widget.*
import android.widget.AdapterView

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var position: TextView
    private lateinit var logView: TextView
    private lateinit var injectionToggle: CheckBox
    private var inject = false
    private var reconnectDelay = 1500L
    private val required get() = buildList {
        if (Build.VERSION.SDK_INT >= 31) add(Manifest.permission.BLUETOOTH_CONNECT)
        if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
    }.toTypedArray()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = 0xff101419.toInt(); window.navigationBarColor = 0xff101419.toInt()
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(22, 28, 22, 18); setBackgroundColor(0xff101419.toInt()) }
        fun label(text: String, size: Float = 15f) = TextView(this).apply { this.text = text; textSize = size; setTextColor(0xffe7edf3.toInt()); setPadding(0, 7, 0, 7) }
        root.addView(label("BeamNG.earth GPS Bridge", 24f))
        status = label("Bluetooth en attente • aucune position injectée")
        root.addView(status)
        position = label("Dernière position : aucune\nÂge du message : —", 14f); root.addView(position)
        root.addView(label("Délai de reconnexion Bluetooth"))
        val retryPicker = Spinner(this)
        retryPicker.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, listOf("1,5 seconde", "5 secondes", "10 secondes"))
        retryPicker.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                reconnectDelay = listOf(1500L, 5000L, 10000L)[position]
                BridgeService.setReconnectDelay(reconnectDelay)
            }
        }
        root.addView(retryPicker)
        root.addView(label("Démarrez la réception ici. Le connecteur Windows se connectera au téléphone appairé via Bluetooth RFCOMM.", 13f))
        root.addView(Button(this).apply { text = "Démarrer la réception Bluetooth"; setOnClickListener { requestThenStart() } })
        root.addView(Button(this).apply { text = "Arrêter le service"; setOnClickListener { stopService(Intent(this@MainActivity, BridgeService::class.java)); status.text = "Service arrêté" } })
        injectionToggle = CheckBox(this).apply {
            text = "Activer l’injection de localisation"; setTextColor(0xffe7edf3.toInt())
            setOnCheckedChangeListener { _, checked ->
                if (checked && checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION), 12)
                } else {
                    inject = checked; BridgeService.setInjection(checked); updateStatus()
                }
            }
        }
        root.addView(injectionToggle)
        root.addView(Button(this).apply { text = "Options pour les développeurs"; setOnClickListener { startActivity(Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS)) } })
        root.addView(label("À configurer manuellement : Options pour les développeurs → Application de localisation fictive → BeamNG GPS Bridge.", 13f))
        root.addView(Button(this).apply { text = "Effacer le journal local"; setOnClickListener { BridgeService.clearLog(); Toast.makeText(this@MainActivity, "Journal effacé", Toast.LENGTH_SHORT).show() } })
        root.addView(Button(this).apply { text = "Copier le rapport diagnostic"; setOnClickListener { copyReport() } })
        root.addView(label("Journal", 18f))
        logView = TextView(this).apply { textSize = 12f; setTextColor(0xffb5c1cd.toInt()); text = BridgeService.logText() }
        val scroll = ScrollView(this).apply { addView(logView); layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f) }; root.addView(scroll)
        setContentView(root)
        Handler(Looper.getMainLooper()).post(object : Runnable { override fun run() {
            status.text = "${BridgeService.connectionState} • ${if (inject) "injection demandée" else "réception seule"}"
            val age = if (BridgeService.lastPositionWallMs == 0L) null else (System.currentTimeMillis() - BridgeService.lastPositionWallMs).coerceAtLeast(0)
            position.text = "Dernière position : ${BridgeService.latestPositionText}\nÂge du message : ${age?.let { "$it ms" } ?: "—"}"
            logView.text = BridgeService.logText()
            window.decorView.postDelayed(this, 1000)
        } })
    }

    private fun requestThenStart() {
        val missing = required.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) { requestPermissions(missing.toTypedArray(), 11); return }
        startReceiver()
    }

    private fun startReceiver() {
        startForegroundService(Intent(this, BridgeService::class.java).putExtra("inject", inject))
        status.text = "Réception RFCOMM démarrée • en attente du connecteur Windows"
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 11 && required.all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }) startReceiver()
        else if (requestCode == 11) status.text = "Autorisation Bluetooth requise; aucune liaison démarrée"
        else if (requestCode == 12) {
            inject = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            BridgeService.setInjection(inject)
            if (!inject) injectionToggle.isChecked = false
            else updateStatus()
        }
    }

    private fun updateStatus() { status.text = if (inject) "Injection demandée • elle ne sera active qu'après réception valide et activation du fournisseur fictif" else "Injection suspendue" }

    private fun copyReport() {
        val permissions = required.joinToString("\n") { "$it : ${if (checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED) "accordée" else "refusée"}" }
        val report = """BeamNG GPS Bridge — diagnostic
Fabricant/modèle : ${Build.MANUFACTURER} ${Build.MODEL}
Android : ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})
One UI : non détectée
Connexion : ${BridgeService.connectionState}
Injection activée dans l'application : $inject
Reconnexion Bluetooth : délai ${reconnectDelay} ms
Position reçue : ${if (BridgeService.lastPositionWallMs > 0) "oui (coordonnées omises du rapport), âge ${System.currentTimeMillis() - BridgeService.lastPositionWallMs} ms" else "non"}
Permissions :
$permissions
Événements récents :
${BridgeService.logText()}
""".trimIndent()
        (getSystemService(CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("Rapport BeamNG GPS Bridge", report))
        Toast.makeText(this, "Rapport copié (sans coordonnées ni identifiants Bluetooth)", Toast.LENGTH_SHORT).show()
    }
}
