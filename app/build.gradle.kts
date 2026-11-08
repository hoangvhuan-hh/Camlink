plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "vn.vinalite.camlink"
    compileSdk = 34
    defaultConfig {
        applicationId = "vn.vinalite.camlink"
        minSdk = 24
        targetSdk = 34
        versionCode = 11
        versionName = "1.4.5"
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64") }
    }
    signingConfigs {
        create("chung") {
            // Khoá ký CỐ ĐỊNH: mọi bản build ra cùng chữ ký → cài đè được, không phải gỡ app.
            storeFile = file("camlink.jks")
            storePassword = "camlink123"
            keyAlias = "camlink"
            keyPassword = "camlink123"
        }
    }
    buildTypes {
        getByName("debug") { signingConfig = signingConfigs.getByName("chung") }
        getByName("release") { isMinifyEnabled = false }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            install("requests")
            install("openpyxl")
            install("rsa")
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.media3:media3-exoplayer:1.3.1")
    implementation("androidx.media3:media3-exoplayer-rtsp:1.3.1")
    implementation("androidx.media3:media3-ui:1.3.1")
}
