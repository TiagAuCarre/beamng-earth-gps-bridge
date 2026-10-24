plugins { id("com.android.application") }

android {
    namespace = "earth.beamng.gpsbridge"
    compileSdk = 37
    defaultConfig { applicationId = "earth.beamng.gpsbridge"; minSdk = 29; targetSdk = 35; versionCode = 2; versionName = "1.0.1" }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
