package nl.ronamersfoort.astroweb.tv

import android.app.SearchManager
import android.content.Intent
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Bundle
import android.provider.MediaStore
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.media3.common.Player
import java.text.Normalizer
import java.util.Locale

internal class Spoken(val text:String)
internal data class Destination(val view:String,val objectId:String?=null)

private fun normalized(s:String):String = Normalizer.normalize(s.lowercase(Locale.ROOT),Normalizer.Form.NFD)
    .replace(Regex("\\p{M}+"),"").replace(Regex("[^a-z0-9]+")," ").trim()
    .replace(Regex("\\b(messier|m|ngc|ic)\\s*(\\d+)\\b")) {
        (if(it.groupValues[1]=="messier") "m" else it.groupValues[1])+it.groupValues[2]
    }.replace(Regex("\\b(messier|m) (eenendertig|thirty one)\\b"),"m31")

internal fun destination(query:String,photos:List<Photo>,selected:String?):Destination? {
    val q=" "+normalized(query)+" "
    fun has(vararg words:String)=words.any { " $it " in q }
    if(has("hemelatlas","sky atlas","personal atlas"))return Destination("atlas")
    if(has("nachtpanorama","night panorama"))return Destination("panorama")
    if(has("opnamekalender","kalender","calendar","observatorium","observatory"))return Destination("calendar")
    if(has("galerij","gallery"))return Destination("gallery")
    val view=when {
        has("sterren in 3d","stars in 3d","stars in three d") -> "space"
        has("lichtreis","light journey") -> "cosmic"
        has("mozaiek","mosaic") -> "mosaic"
        has("zonvergelijking","solar comparison") -> "solar"
        has("poolkaart","polar chart","polar map") -> "polar"
        has("skykaart","sky chart") -> "sky"
        has("melkwegkaart","melkweg","milky way map") -> "galaxy"
        has("hubble","journeys","reizen") -> "trips"
        has("hemelreis","sky journey") -> "skyjourney"
        has("foto","photo","original","origineel") -> "photo"
        else -> "film"
    }
    val matches=photos.filter { p ->
        val terms=listOf(p.catalog,p.name.nl,p.name.en,p.posterName(false),p.posterName(true)) + p.aliases +
            listOf(p.name.en.removeSuffix(" Galaxy"),p.name.nl.removeSuffix("stelsel"),p.posterName(false).removeSuffix("gebied"))
        terms.map(::normalized).any { it.isNotBlank() && " $it " in q }
    }
    val target=matches.singleOrNull()?.id ?: if(matches.isEmpty() && q.trim() in setOf(
        "open de foto","show the photo","open reizen","open journeys","open de poolkaart","open polar chart",
        "open de skykaart","open sky chart","speel af","play","open de melkwegkaart","open milky way map",
        "open sterren in 3d","show stars in 3d","open de lichtreis","open light journey","open het mozaiek","open mosaic","open zonvergelijking","open solar comparison"))selected else null
    return target?.let { Destination(view,it) }
}

internal fun spokenIntent(intent:Intent?):Spoken? {
    if(intent?.action !in setOf(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH,Intent.ACTION_SEARCH))return null
    val q=intent?.getStringExtra(SearchManager.QUERY).orEmpty()
    return Spoken(q.take(300).ifBlank { "play" })
}

@Composable internal fun AssistantPlayback(player:Player,title:String,foreground:Boolean,setPlaying:(Boolean)->Unit) {
    val context=LocalContext.current
    val control by rememberUpdatedState(setPlaying)
    DisposableEffect(player,title,foreground) {
        if(!foreground)return@DisposableEffect onDispose {}
        val session=MediaSession(context,"AstroWeb TV")
        val actions=PlaybackState.ACTION_PLAY or PlaybackState.ACTION_PAUSE or PlaybackState.ACTION_PLAY_PAUSE or PlaybackState.ACTION_PLAY_FROM_SEARCH
        fun publish() {
            val state=when {
                player.playbackState==Player.STATE_BUFFERING && player.playWhenReady -> PlaybackState.STATE_BUFFERING
                player.isPlaying -> PlaybackState.STATE_PLAYING
                else -> PlaybackState.STATE_PAUSED
            }
            session.setPlaybackState(PlaybackState.Builder().setActions(actions)
                .setState(state,player.currentPosition,if(player.isPlaying) 1f else 0f).build())
        }
        session.setCallback(object:MediaSession.Callback(){
            override fun onPlay(){control(true)}
            override fun onPause(){control(false)}
            override fun onPlayFromSearch(query:String?,extras:Bundle?) {
                if(query.isNullOrBlank())control(true) else context.startActivity(Intent(context,MainActivity::class.java)
                    .setAction(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).putExtra(SearchManager.QUERY,query)
                    .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP))
            }
        })
        session.setMetadata(MediaMetadata.Builder().putString(MediaMetadata.METADATA_KEY_TITLE,title).build())
        val listener=object:Player.Listener { override fun onEvents(p:Player,events:Player.Events){publish()} }
        player.addListener(listener);publish();session.isActive=true
        onDispose { player.removeListener(listener);session.isActive=false;session.release() }
    }
}
