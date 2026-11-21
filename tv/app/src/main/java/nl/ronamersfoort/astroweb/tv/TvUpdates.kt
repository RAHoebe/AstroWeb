package nl.ronamersfoort.astroweb.tv

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.pm.PackageInfoCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.File
import java.net.URL
import java.security.MessageDigest
import javax.net.ssl.HttpsURLConnection

private const val repository = "RAHoebe/AstroWeb"
private const val maxApkBytes = 100L * 1024 * 1024
private val releaseTag = Regex("""tv-v(\d+\.\d+\.\d+)""")
private val sha256 = Regex("[0-9a-f]{64}")

internal data class TvUpdate(val version: String, val name: String, val bytes: Long, val digest: String) :
    java.io.Serializable {
    val url: String get() = "https://github.com/$repository/releases/download/tv-v$version/$name"
}

private data class Version(val major: Int, val minor: Int, val patch: Int) : Comparable<Version> {
    override fun compareTo(other: Version) = compareValuesBy(this, other, Version::major, Version::minor, Version::patch)

    companion object {
        fun parse(value: String): Version? {
            val parts = value.split('.').map { it.toIntOrNull() ?: return null }
            return if (parts.size == 3) Version(parts[0], parts[1], parts[2]) else null
        }
    }
}

private fun connection(address: String) = (URL(address).openConnection() as HttpsURLConnection).apply {
    connectTimeout = 6_000
    readTimeout = 10_000
    setRequestProperty("User-Agent", "AstroWeb-TV/${BuildConfig.VERSION_NAME}")
}

internal suspend fun findTvUpdate(): TvUpdate? = withContext(Dispatchers.IO) {
    val current = Version.parse(BuildConfig.VERSION_NAME) ?: return@withContext null
    val edition = if (BuildConfig.LAN_ONLY) "AstroWeb-TV-LAN" else "AstroWeb-TV"
    val request = connection("https://api.github.com/repos/$repository/releases?per_page=100")
    request.instanceFollowRedirects = false
    request.setRequestProperty("Accept", "application/vnd.github+json")
    request.setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
    val releases = try {
        check(request.responseCode == 200)
        JSONArray(request.inputStream.bufferedReader().use { it.readText() })
    } finally {
        request.disconnect()
    }

    var latest: TvUpdate? = null
    var latestVersion = current
    for (i in 0 until releases.length()) {
        val release = releases.optJSONObject(i) ?: continue
        if (release.optBoolean("draft") || release.optBoolean("prerelease")) continue
        val tag = releaseTag.matchEntire(release.optString("tag_name")) ?: continue
        val version = tag.groupValues[1]
        val parsed = Version.parse(version) ?: continue
        if (parsed <= latestVersion) continue
        val assets = release.optJSONArray("assets") ?: continue
        val name = "$edition-$version.apk"
        for (j in 0 until assets.length()) {
            val asset = assets.optJSONObject(j) ?: continue
            if (asset.optString("name") != name || asset.optString("state") != "uploaded") continue
            val digest = asset.optString("digest").removePrefix("sha256:")
            val update = TvUpdate(version, name, asset.optLong("size"), digest)
            if (update.bytes !in 1..maxApkBytes || !sha256.matches(digest)) continue
            if (asset.optString("browser_download_url") != update.url) continue
            latestVersion = parsed
            latest = update
            break
        }
    }
    latest
}

internal suspend fun downloadTvUpdate(context: Context, update: TvUpdate): File = withContext(Dispatchers.IO) {
    val directory = File(context.cacheDir, "updates").apply { mkdirs() }
    directory.listFiles()?.forEach {
        if (it.lastModified() < System.currentTimeMillis() - 86_400_000L) it.delete()
    }
    val file = File.createTempFile("astroweb-", ".apk", directory)
    val digest = MessageDigest.getInstance("SHA-256")
    val request = connection(update.url)
    try {
        check(request.responseCode == 200)
        var total = 0L
        request.inputStream.use { input ->
            file.outputStream().use { output ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    ensureActive()
                    val count = input.read(buffer)
                    if (count == -1) break
                    total += count
                    check(total <= update.bytes)
                    digest.update(buffer, 0, count)
                    output.write(buffer, 0, count)
                }
            }
        }
        check(total == update.bytes && digest.digest().joinToString("") { "%02x".format(it) } == update.digest)
        verifyTvUpdate(context, file, update)
        file
    } catch (e: Exception) {
        file.delete()
        throw e
    } finally {
        request.disconnect()
    }
}

@Suppress("DEPRECATION")
private fun verifyTvUpdate(context: Context, file: File, update: TvUpdate) {
    val manager = context.packageManager
    val flags = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES
    val apk = checkNotNull(manager.getPackageArchiveInfo(file.path, flags))
    check(apk.packageName == context.packageName && apk.versionName == update.version &&
        PackageInfoCompat.getLongVersionCode(apk) > BuildConfig.VERSION_CODE)
    fun signers(info: PackageInfo) = if (Build.VERSION.SDK_INT >= 28) {
        info.signingInfo?.apkContentsSigners.orEmpty().toSet()
    } else {
        info.signatures.orEmpty().toSet()
    }
    val expected = signers(manager.getPackageInfo(context.packageName, flags))
    check(expected.isNotEmpty() && signers(apk) == expected)
}
