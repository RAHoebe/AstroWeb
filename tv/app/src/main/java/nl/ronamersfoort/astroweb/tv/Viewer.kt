package nl.ronamersfoort.astroweb.tv

import android.view.KeyEvent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.BiasAlignment
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.*
import androidx.compose.ui.graphics.Color
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

@Composable internal fun Viewer(initialId: String, en: Boolean, foreground: Boolean, leave: ()->Unit) {
    var capture by rememberSaveable { mutableStateOf(initialId) }
    var full by rememberSaveable { mutableStateOf(false) }
    var filled by rememberSaveable { mutableStateOf(false) }
    var panX by rememberSaveable { mutableFloatStateOf(0f) }
    var panY by rememberSaveable { mutableFloatStateOf(0f) }
    var film by rememberSaveable { mutableStateOf(true) }
    var playing by rememberSaveable { mutableStateOf(true) }
    var trips by rememberSaveable { mutableStateOf(false) }
    var maps by rememberSaveable { mutableStateOf(false) }
    val mapsButton=remember { FocusRequester() }
    val tripsButton = remember { FocusRequester() }
    var choosingDate by remember { mutableStateOf(false) }
    var retry by remember { mutableIntStateOf(0) }
    var photo by remember(capture) { mutableStateOf<Photo?>(null) }
    var failed by remember(capture) { mutableStateOf(false) }
    val first = remember { FocusRequester() }
    val fullButton = remember { FocusRequester() }
    val fillButton = remember { FocusRequester() }
    val canvas = remember { FocusRequester() }
    val dates = remember { FocusRequester() }
    var focusReturn by remember { mutableStateOf("first") }
    fun back() {
        when {
            full -> { focusReturn = if (filled) "fill" else "full"; full = false; filled = false }
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
    LaunchedEffect(p, full, choosingDate, failed, trips, maps) {
        if (trips || maps) return@LaunchedEffect
        if (p != null) {
            when {
                full -> canvas
                choosingDate -> currentDate
                focusReturn == "maps" -> mapsButton
                focusReturn == "trips" -> tripsButton
                focusReturn == "full" -> fullButton
                focusReturn == "fill" -> fillButton
                focusReturn == "dates" && p.captures.size > 1 -> dates
                else -> first
            }.requestFocus()
        } else if (failed) first.requestFocus()
    }
    if (maps && p != null) {
        Maps(p,en,foreground) { focusReturn="maps"; maps=false }
        return
    }
    if (trips && p != null) {
        Travel(p,en,foreground) { focusReturn="trips"; trips=false }
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
                        Movie(p.film, playing, foreground, filled, en)
                    } else {
                        var attempt by remember(p.original) { mutableIntStateOf(0) }
                        key(p.original,attempt) {
                            val context=LocalContext.current
                            val model=remember(p.original,context) { ImageRequest.Builder(context).data(p.original)
                                .transformations(LandscapePhoto).build() }
                            SubcomposeAsyncImage(model, p.name.get(en), Modifier.fillMaxSize(),
                                alignment=if(filled) BiasAlignment(panX,panY) else Alignment.Center, contentScale=if(filled) ContentScale.Crop else ContentScale.Fit,
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
                            Text(p.name.get(en),color=light,fontSize=21.sp)
                            Spacer(Modifier.width(14.dp))
                            Text(p.catalog.replace('_',' ')+"   ·   "+dateLabel(p.date,en),color=quiet,fontSize=14.sp)
                        }
                        Spacer(Modifier.height(7.dp))
                        Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(6.dp)) {
                            if (choosingDate) {
                                for (item in p.captures) {
                                    val isCurrent = item.id == capture
                                    Action(dateLabel(item.date,en), if(isCurrent) Modifier.focusRequester(currentDate) else Modifier, isCurrent) {
                                        focusReturn="dates"; choosingDate=false; capture=item.id
                                    }
                                }
                            } else {
                                if(p.film!=null) Action("Film", Modifier.focusRequester(first),film,icon=R.drawable.ic_film) { if(!film) playing=true;film=true }
                                Action(if(en) "Photo" else "Foto",if(p.film==null) Modifier.focusRequester(first) else Modifier,!film || p.film==null,icon=R.drawable.ic_photo) { film=false }
                                if(film && p.film!=null) Action(if(playing) (if(en) "Pause" else "Pauze") else (if(en) "Play" else "Afspelen"),
                                    icon=if(playing) R.drawable.ic_pause else R.drawable.ic_play) { playing=!playing }
                                Action(if(en) "Journeys" else "Reizen", Modifier.focusRequester(tripsButton),icon=R.drawable.ic_route) { trips=true }
                                if (p.maps) Action(if(en) "Maps" else "Kaarten", Modifier.focusRequester(mapsButton),icon=R.drawable.ic_maps) { maps=true }
                                if (p.captures.size>1) Action(if(en) "Capture date" else "Opnamedatum",Modifier.focusRequester(dates),icon=R.drawable.ic_date) { choosingDate=true }
                                Action(if(en) "Full screen" else "Volledig scherm", Modifier.focusRequester(fullButton),icon=R.drawable.ic_full) { full=true }
                                Action(if(en) "Fill screen" else "Vul scherm", Modifier.focusRequester(fillButton),icon=R.drawable.ic_fill) {
                                    panX=0f; panY=0f; filled=true; full=true
                                }
                                Action(if(en) "Gallery" else "Galerij",icon=R.drawable.ic_gallery, run=leave)
                            }
                        }
                    }
                }
            }
            if(full) Box(Modifier.fillMaxSize().focusRequester(canvas).onPreviewKeyEvent { e ->
                val ev=e.nativeKeyEvent
                if (filled && (!film || p.film==null) && ev.keyCode in listOf(KeyEvent.KEYCODE_DPAD_LEFT,KeyEvent.KEYCODE_DPAD_RIGHT,KeyEvent.KEYCODE_DPAD_UP,KeyEvent.KEYCODE_DPAD_DOWN)) {
                    if (ev.action==KeyEvent.ACTION_DOWN) when(ev.keyCode) {
                        KeyEvent.KEYCODE_DPAD_LEFT -> panX=(panX-.16f).coerceAtLeast(-1f)
                        KeyEvent.KEYCODE_DPAD_RIGHT -> panX=(panX+.16f).coerceAtMost(1f)
                        KeyEvent.KEYCODE_DPAD_UP -> panY=(panY-.16f).coerceAtLeast(-1f)
                        KeyEvent.KEYCODE_DPAD_DOWN -> panY=(panY+.16f).coerceAtMost(1f)
                    }
                    true
                } else if (ev.keyCode in listOf(KeyEvent.KEYCODE_DPAD_CENTER,KeyEvent.KEYCODE_ENTER,KeyEvent.KEYCODE_NUMPAD_ENTER)) {
                    if (ev.action==KeyEvent.ACTION_UP) back()
                    true
                } else false
            }.focusable())
        }
    }
}

@Composable private fun Message(value: String) {
    Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center) { Text(value,color=quiet,fontSize=16.sp) }
}

@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
@Composable internal fun Movie(url:String, playing:Boolean, foreground:Boolean, filled:Boolean, en:Boolean, onFailure: (Boolean)->Unit = {}) {
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
    AndroidView(factory={ ctx -> android.view.LayoutInflater.from(ctx).inflate(R.layout.movie_surface,null) as PlayerView },update={ it.player=player; it.resizeMode=if(filled) androidx.media3.ui.AspectRatioFrameLayout.RESIZE_MODE_ZOOM else androidx.media3.ui.AspectRatioFrameLayout.RESIZE_MODE_FIT;it.keepScreenOn=playing && foreground && !failed },modifier=Modifier.fillMaxSize().landscapeVideo(tall))
    if (buffering) Message(if(en) "Loading film…" else "Film laden…")
    if (failed) Action(if(en) "Reload film" else "Film opnieuw laden", Modifier.focusRequester(errorFocus)) { failed=false;player.prepare() }
}
