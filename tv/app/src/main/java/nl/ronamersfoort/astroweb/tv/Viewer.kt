package nl.ronamersfoort.astroweb.tv

import android.view.KeyEvent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.*
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.*
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.tv.material3.Text
import coil.request.ImageRequest
import coil.compose.SubcomposeAsyncImage
import kotlinx.coroutines.CancellationException
import kotlin.math.roundToInt

@Composable internal fun Viewer(initialId: String, en: Boolean, foreground: Boolean, entry:String="film", gallery:(String)->Unit, leave: ()->Unit) {
    var capture by rememberSaveable { mutableStateOf(initialId) }
    var full by rememberSaveable { mutableStateOf(false) }
    var film by rememberSaveable { mutableStateOf(entry!="photo") }
    var turns by rememberSaveable(capture,film) { mutableIntStateOf(0) }
    var playing by rememberSaveable { mutableStateOf(true) }
    var trips by rememberSaveable { mutableStateOf(entry=="trips" || entry=="skyjourney") }
    var maps by rememberSaveable { mutableStateOf(entry in listOf("sky","polar","galaxy")) }
    val mapsButton=remember { FocusRequester() }
    val tripsButton = remember { FocusRequester() }
    var explore by rememberSaveable { mutableStateOf(false) }
    var observatory by rememberSaveable { mutableStateOf(entry in listOf("space","cosmic","mosaic","solar")) }
    var observatoryMode by rememberSaveable { mutableStateOf(entry) }
    val featureFocus=remember { listOf("space","cosmic","mosaic","solar").associateWith { FocusRequester() } }
    val exploreButton=remember { FocusRequester() }
    var choosingDate by remember { mutableStateOf(false) }
    var retry by remember { mutableIntStateOf(0) }
    var photo by remember(capture) { mutableStateOf<Photo?>(null) }
    var failed by remember(capture) { mutableStateOf(false) }
    val first = remember { FocusRequester() }
    val fullButton = remember { FocusRequester() }
    val canvas = remember { FocusRequester() }
    val dates = remember { FocusRequester() }
    var firstDestination by rememberSaveable { mutableStateOf(entry) }
    var focusReturn by remember { mutableStateOf("first") }
    fun back() {
        when {
            full -> { focusReturn="full";full=false }
            choosingDate -> { focusReturn = "dates"; choosingDate = false }
            else -> leave()
        }
    }
    BackHandler { back() }
    LaunchedEffect(capture,retry) {
        failed = false
        try { photo = detail(capture) }
        catch (e: CancellationException) { throw e }
        catch (_: Exception) { failed = true }
    }
    val p = photo
    val currentDate = remember { FocusRequester() }
    LaunchedEffect(p, full, choosingDate, failed, trips, maps, explore, observatory) {
        if (trips || maps || explore || observatory) return@LaunchedEffect
        if (p != null) {
            when {
                full && film && p.film!=null -> canvas
                full -> return@LaunchedEffect
                choosingDate -> currentDate
                focusReturn == "explore" -> exploreButton
                focusReturn == "observatory" -> featureFocus[observatoryMode] ?: first
                focusReturn == "maps" -> mapsButton
                focusReturn == "trips" -> tripsButton
                focusReturn == "full" -> fullButton
                focusReturn == "dates" && p.captures.size > 1 -> dates
                else -> first
            }.requestFocus()
        } else if (failed) first.requestFocus()
    }
    if(full && p!=null && (!film || p.film==null)) {
        RemoteCanvas("photo.html",p.id,"photo",en,foreground=foreground,turns=turns,onRotate={ turns=(turns+1)%4 })
        return
    }
    if (explore && p != null) {
        RemoteCanvas("viewing.html",p.id,"explore",en,foreground=foreground) { focusReturn="explore";explore=false }
        return
    }
    if (observatory && p != null) {
        if(observatoryMode !in p.explorations) {
            val context=LocalContext.current
            LaunchedEffect(observatoryMode) {android.widget.Toast.makeText(context,if(en) "This view is unavailable for this capture" else "Deze weergave is niet beschikbaar voor deze opname",android.widget.Toast.LENGTH_LONG).show();focusReturn="first";observatory=false}
            return
        }
        RemoteCanvas("observatory.html",p.id,observatoryMode,en,foreground=foreground,openCapture={chosen->capture=chosen;observatory=false;film=false}) { focusReturn="observatory";observatory=false }
        return
    }
    if (maps && p != null) {
        Maps(p,en,foreground,firstDestination) { firstDestination="";focusReturn="maps"; maps=false }
        return
    }
    if (trips && p != null) {
        Travel(p,en,foreground,firstDestination=="skyjourney") { firstDestination="";focusReturn="trips"; trips=false }
        return
    }
    Box(Modifier.fillMaxSize().background(Color.Black).onPreviewKeyEvent { e ->
        val ev = e.nativeKeyEvent
        if (film && p?.film!=null && ev.keyCode in listOf(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, KeyEvent.KEYCODE_MEDIA_PAUSE, KeyEvent.KEYCODE_MEDIA_PLAY)) {
            if (ev.action == KeyEvent.ACTION_UP) playing = when(ev.keyCode) {
                KeyEvent.KEYCODE_MEDIA_PLAY -> true
                KeyEvent.KEYCODE_MEDIA_PAUSE -> false
                else -> !playing
            }
            true
        } else false
    }) {
        if (p == null) {
            Column(Modifier.align(Alignment.Center),horizontalAlignment=Alignment.CenterHorizontally) {
                Text(if (failed) (if (en) "Capture unavailable" else "Opname niet beschikbaar")
                    else (if (en) "Loading capture…" else "Opname laden…"), color=light)
                if (failed) Action(if (en) "Try again" else "Opnieuw proberen",Modifier.focusRequester(first)) { retry++ }
            }
        } else {
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment=Alignment.Center) {
                    if (film && p.film != null) {
                        Movie(p.film, playing, foreground, en,turns,p.name.get(en),{ playing=it })
                    } else {
                        var attempt by remember(p.original) { mutableIntStateOf(0) }
                        key(p.original,attempt) {
                            val context=LocalContext.current
                            val model=remember(p.original,context) { ImageRequest.Builder(context).data(p.original)
                                .transformations(LandscapePhoto).build() }
                            SubcomposeAsyncImage(model, p.name.get(en), Modifier.fillMaxSize().quarterTurns(turns),
                                alignment=Alignment.Center, contentScale=ContentScale.Fit,
                                loading={ Message(if(en) "Loading photo…" else "Foto laden…") },
                                error={ Box(Modifier.fillMaxSize(), contentAlignment=Alignment.Center) {
                                    Action(if(en) "Reload photo" else "Foto opnieuw laden") { attempt++ }
                                } })
                        }
                    }
                }
                if (!full) {
                    Column(Modifier.fillMaxWidth().background(ink).padding(start=40.dp,end=40.dp,top=8.dp,bottom=14.dp)) {
                        Row(verticalAlignment=Alignment.CenterVertically) {
                            Text(p.posterName(en),color=light,fontSize=21.sp)
                            Spacer(Modifier.width(14.dp))
                            Text(p.catalog.replace('_',' ')+"   ·   "+dateLabel(p.date,en),color=quiet,fontSize=14.sp)
                        }
                        Spacer(Modifier.height(7.dp))
                        ViewerActionRow(choosingDate) {
                            if (choosingDate) {
                                for (item in p.captures) {
                                    val isCurrent = item.id == capture
                                    Action(dateLabel(item.date,en), if(isCurrent) Modifier.focusRequester(currentDate) else Modifier, isCurrent) {
                                        focusReturn="dates"; choosingDate=false; capture=item.id
                                    }
                                }
                            } else {
                                if(p.film!=null) Action("Film", Modifier.focusRequester(first),film,icon=R.drawable.ic_film,compact=true) { if(!film) playing=true;film=true }
                                Action(if(en) "Photo" else "Foto",if(p.film==null) Modifier.focusRequester(first) else Modifier,!film || p.film==null,icon=R.drawable.ic_photo,compact=true) { film=false }
                                if(film && p.film!=null) Action(if(playing) (if(en) "Pause" else "Pauze") else (if(en) "Play" else "Afspelen"),
                                    icon=if(playing) R.drawable.ic_pause else R.drawable.ic_play,compact=true) { playing=!playing }
                                Action(if(en) "Journeys" else "Reizen", Modifier.focusRequester(tripsButton),icon=R.drawable.ic_route,compact=true) { trips=true }
                                if (p.maps) Action(if(en) "Maps" else "Kaarten", Modifier.focusRequester(mapsButton),icon=R.drawable.ic_maps,compact=true) { maps=true }
                                if (p.captures.size>1) Action(if(en) "Capture date" else "Opnamedatum",Modifier.focusRequester(dates),icon=R.drawable.ic_date,compact=true) { choosingDate=true }
                                Action(if(en) "Explore" else "Verken", Modifier.focusRequester(exploreButton),icon=R.drawable.ic_explore,compact=true) { explore=true }
                                for(feature in listOf("space","cosmic","mosaic","solar").filter { it in p.explorations }) {
                                    val name=when(feature) {"space" -> if(en) "Stars in 3D" else "Sterren in 3D";"cosmic" -> if(en) "Light journey" else "Lichtreis";"mosaic" -> if(en) "Mosaic" else "Mozaïek";else -> if(en) "Solar comparison" else "Zonvergelijking"}
                                    Action(name,Modifier.focusRequester(featureFocus.getValue(feature)),icon=R.drawable.ic_star,compact=true) {observatoryMode=feature;observatory=true}
                                }
                                Action(if(en) "Gallery" else "Galerij",icon=R.drawable.ic_gallery,compact=true) { gallery(capture) }
                                Action(if(en) "Rotate 90°" else "Draai 90°",icon=R.drawable.ic_rotate,iconOnly=true,compact=true) { turns=(turns+1)%4 }
                                Action(if(en) "Full screen" else "Volledig scherm",Modifier.focusRequester(fullButton),icon=R.drawable.ic_full,iconOnly=true,compact=true) { full=true }
                            }
                        }
                    }
                }
            }
            if(full) {
                var hint by remember { mutableStateOf(true) }
                LaunchedEffect(turns) { hint=true;kotlinx.coroutines.delay(2400);hint=false }
                if(hint) Text((if(en) "← →  Rotate" else "← →  Draai")+"  "+turns*90+"°",Modifier.align(Alignment.TopStart)
                    .padding(24.dp).background(ink.copy(alpha=.88f)).padding(6.dp),color=light,fontSize=14.sp)
            }
            if(full) Box(Modifier.fillMaxSize().focusRequester(canvas).onPreviewKeyEvent { e ->
                val ev=e.nativeKeyEvent
                if(ev.keyCode==KeyEvent.KEYCODE_DPAD_LEFT || ev.keyCode==KeyEvent.KEYCODE_DPAD_RIGHT) {
                    if(ev.action==KeyEvent.ACTION_UP) turns=(turns+if(ev.keyCode==KeyEvent.KEYCODE_DPAD_RIGHT) 1 else 3)%4
                    true
                } else if (ev.keyCode in listOf(KeyEvent.KEYCODE_DPAD_CENTER,KeyEvent.KEYCODE_ENTER,KeyEvent.KEYCODE_NUMPAD_ENTER)) {
                    if (ev.action==KeyEvent.ACTION_UP) back()
                    true
                } else false
            }.focusable())
        }
    }
}

// Fit every available action on one row. The last two icon buttons stay at the
// right edge; proportional scaling is only needed for captures with many views.
@Composable private fun ViewerActionRow(dates:Boolean, content:@Composable ()->Unit) {
    if(dates) {
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(5.dp)) { content() }
        return
    }
    Layout(content=content,modifier=Modifier.fillMaxWidth()) { measurables,limits ->
        val items=measurables.map { it.measure(limits.copy(minWidth=0,maxWidth=Constraints.Infinity,minHeight=0)) }
        val gap=5.dp.roundToPx()
        val natural=items.sumOf { it.width }+gap*(items.size-1).coerceAtLeast(0)
        val width=if(limits.hasBoundedWidth) limits.maxWidth else natural
        val scale=if(natural>0) minOf(1f,width.toFloat()/natural) else 1f
        val height=((items.maxOfOrNull { it.height } ?: 0)*scale).roundToInt()
        layout(width,limits.constrainHeight(height)) {
            var x=0f
            val spare=(width-natural*scale).coerceAtLeast(0f)
            items.forEachIndexed { index,item ->
                if(index==items.size-2)x+=spare
                item.placeWithLayer(x.roundToInt(),0) {
                    scaleX=scale;scaleY=scale;transformOrigin=TransformOrigin(0f,0f)
                }
                x+=(item.width+gap)*scale
            }
        }
    }
}

@Composable private fun Message(value: String) {
    Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center) { Text(value,color=quiet,fontSize=16.sp) }
}

@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
@Composable internal fun Movie(url:String, playing:Boolean, foreground:Boolean, en:Boolean, turns:Int, title:String, setPlaying:(Boolean)->Unit, onFailure: (Boolean)->Unit = {}) {
    val context=LocalContext.current
    var failed by remember(url) { mutableStateOf(false) }
    var buffering by remember(url) { mutableStateOf(true) }
    var tall by remember(url) { mutableStateOf(false) }
    val errorFocus=remember { FocusRequester() }
    LaunchedEffect(failed,url) { onFailure(failed); if(failed) errorFocus.requestFocus() }
    val player=remember(url) {
        val http = androidx.media3.datasource.DefaultHttpDataSource.Factory().setReadTimeoutMs(240000)
        ExoPlayer.Builder(context).setMediaSourceFactory(androidx.media3.exoplayer.source.DefaultMediaSourceFactory(http)).build()
    }
    AssistantPlayback(player,title,foreground,setPlaying)
    DisposableEffect(player) {
        val listener=object:Player.Listener {
            override fun onVideoSizeChanged(size: VideoSize) { tall = size.height > size.width * size.pixelWidthHeightRatio }
            override fun onPlaybackStateChanged(state:Int) { buffering=state==Player.STATE_BUFFERING }
            override fun onPlayerError(error: PlaybackException) { failed=true;buffering=false }
        }
        player.addListener(listener);player.repeatMode=Player.REPEAT_MODE_ONE
        player.setMediaItem(MediaItem.fromUri(url));player.prepare()
        onDispose { player.removeListener(listener);player.release() }
    }
    LaunchedEffect(player,playing,foreground) { player.playWhenReady=playing && foreground }
    AndroidView(factory={ ctx -> android.view.LayoutInflater.from(ctx).inflate(R.layout.movie_surface,null) as PlayerView },update={ it.player=player; it.resizeMode=androidx.media3.ui.AspectRatioFrameLayout.RESIZE_MODE_FIT;it.keepScreenOn=playing && foreground && !failed },onRelease={it.player=null;it.keepScreenOn=false},modifier=Modifier.fillMaxSize().quarterTurns(turns - if(tall) 1 else 0))
    if (buffering) Message(if(en) "Loading film…" else "Film laden…")
    if (failed) Action(if(en) "Reload film" else "Film opnieuw laden", Modifier.focusRequester(errorFocus)) { failed=false;player.prepare() }
}
