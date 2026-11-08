pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
        maven("https://chaquo.com/maven")
    }
}
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven("https://chaquo.com/maven")
    }
}
rootProject.name = "CamLink"
include(":app")
