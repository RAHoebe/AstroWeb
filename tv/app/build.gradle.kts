plugins {
    id("com.android.application") version "9.1.0"
    id("org.jetbrains.kotlin.plugin.compose") version "2.2.10"
}

android {
    namespace = "nl.ronamersfoort.astroweb.tv"
    compileSdk = 36
    defaultConfig {
        applicationId = "nl.ronamersfoort.astroweb.tv"
        minSdk = 26
        targetSdk = 36
        versionCode = 14
        versionName = "0.8.1"
    }
    buildFeatures { compose = true; buildConfig = true }
    defaultConfig { buildConfigField("boolean", "LAN_ONLY", "false") }
    buildTypes {
        create("lan") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".lan"
            matchingFallbacks += "debug"
            buildConfigField("boolean", "LAN_ONLY", "true")
        }
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.10.01"))
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.tv:tv-material:1.0.1")
    implementation("androidx.media3:media3-exoplayer:1.8.0")
    implementation("androidx.media3:media3-ui:1.8.0")
    implementation("io.coil-kt:coil-compose:2.7.0")
}
