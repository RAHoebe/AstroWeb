package nl.ronamersfoort.astroweb.tv

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.URL
import javax.net.ssl.HttpsURLConnection

internal const val server = "https://astroweb.ronamersfoort.synology.me"

data class Words(val nl: String, val en: String) {
    fun get(english: Boolean) = if (english) en.ifBlank { nl } else nl.ifBlank { en }
}
data class Capture(val id: String, val date: String)
data class Photo(
    val id: String, val catalog: String, val name: Words, val summary: Words,
    val date: String, val poster: String?, val original: String?, val film: String?,
    val hasHubble: Boolean, val maps: Boolean, val milkyWay: Boolean, val captures: List<Capture>
)

private suspend fun json(path: String): JSONObject = withContext(Dispatchers.IO) {
    val connection = URL(server + path).openConnection() as HttpsURLConnection
    connection.connectTimeout = 8000
    connection.readTimeout = 15000
    try {
        connection.inputStream.bufferedReader(Charsets.UTF_8).use { JSONObject(it.readText()) }
    } finally { connection.disconnect() }
}

private fun JSONArray?.entries() = (0 until (this?.length() ?: 0)).map { this!!.getJSONObject(it) }

private fun JSONObject.media(key: String): String? =
    optString(key).takeIf { it.startsWith("/media/") }?.let { server + it }

private fun JSONObject.words(key: String) = optJSONObject(key).let {
    Words(it?.optString("nl").orEmpty(), it?.optString("en").orEmpty())
}

private fun photo(o: JSONObject): Photo {
    val info = o.getJSONObject("metadata")
    return Photo(o.getString("id"), o.optString("catalog_id", o.getString("id")),
        info.words("name"), info.words("summary"), o.optString("capture_date").take(10),
        o.media("poster"), o.media("original_view") ?: o.media("final"), o.media("video"),
        o.optBoolean("hubble_available"), o.isNull("capture_kind") || o.optString("capture_kind").isBlank(),
        o.optJSONObject("galaxy") != null, o.optJSONArray("captures").entries().map { Capture(it.getString("id"), it.optString("date").take(10)) })
}
suspend fun gallery(): List<Photo> {
    return json("/api/objects").getJSONArray("objects").entries().map(::photo)
}
suspend fun detail(id: String) = photo(json("/api/objects/" + android.net.Uri.encode(id)))

data class Trip(val id: String, val name: Words, val credit: String, val url: String)

suspend fun skyTrip(id: String): Trip? {
    val data = json("/api/objects/" + android.net.Uri.encode(id) + "/journey")
    val url = data.media("url") ?: return null
    return Trip("journey", Words("Hemelreis", "Sky journey"), "", url)
}

private val fieldNames = mapOf(
    "ngc206" to Words("NGC 206 · blauwe sterwolk", "NGC 206 · blue star cloud"),
    "m32" to Words("M32 · satellietstelsel", "M32 · satellite galaxy"),
    "nucleus" to Words("M31 · galactische kern", "M31 · galactic nucleus"),
    "heic0512d" to Words("De stofbanden van Andromeda", "Andromeda’s dust lanes"),
    "heic0510a" to Words("Cygnusmuur en donkere stofwolk", "Cygnus Wall and dark cloud"),
    "c20-wfpc2" to Words("Stofboog bij V1057 Cyg", "Dust arc near V1057 Cyg"),
    "ic1396a" to Words("Olifantenslurf", "Elephant’s Trunk")
)

suspend fun hubbleTrips(capture: String): List<Trip> {
    val path = android.net.Uri.encode(capture)
    var fieldNumber = 0
    return json("/api/objects/$path/hubble").optJSONArray("observations").entries().map { obj ->
        val id = obj.getString("id")
        val target = obj.optString("target").takeUnless { it.uppercase() in setOf("ANY","NONE","PAR","PARALLEL") }.orEmpty()
        val description = obj.optString("title").ifBlank {
            listOf(target, obj.optString("filter")).filter { it.isNotBlank() }.joinToString(" · ")
        }.ifBlank { id }
        if (obj.optBoolean("full_footprint")) fieldNumber++
        val name = fieldNames[id] ?: if (obj.optBoolean("full_footprint"))
            Words("$description · veld $fieldNumber", "$description · field $fieldNumber")
        else Words(description, description)
        Trip(id, name, obj.optString("credit").ifBlank { "NASA / ESA · Hubble" },
            "$server/media/$path/hubble/" + android.net.Uri.encode(id))
    }
}
