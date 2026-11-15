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
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.*
import androidx.tv.material3.Text
import androidx.compose.ui.platform.LocalContext
import coil.request.ImageRequest
import coil.compose.AsyncImage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay

private data class Choices(val items: List<Trip> = emptyList(), val busy: Boolean = true, val error: Boolean = false)

@Composable private fun choices(loadKey: String, attempt: Int, fetch: suspend () -> List<Trip>): Choices {
    return produceState(Choices(),loadKey,attempt) {
        value=Choices()
        value=try { Choices(fetch(),busy=false) }
        catch (e: CancellationException) { throw e }
        catch (_: Exception) { Choices(busy=false,error=true) }
    }.value
}

@Composable internal fun Travel(p: Photo, en: Boolean, foreground: Boolean, leave: () -> Unit) {
    var attempt by remember { mutableIntStateOf(0) }
    val sky=choices(p.id,attempt) { listOfNotNull(skyTrip(p.id)) }
    val hubble=choices(p.id,attempt) { if(p.hasHubble) hubbleTrips(p.id) else emptyList() }
    var selection by rememberSaveable(p.id) { mutableStateOf("journey") }
    var watching by rememberSaveable(p.id) { mutableStateOf(false) }
    val list=sky.items+hubble.items
    val active=list.find { it.id==selection }
    val fallback=remember { FocusRequester() }
    val requesters=remember(list) { list.associate { it.id to FocusRequester() } }
    val scroll=rememberScrollState()
    if (watching && active!=null) {
        JourneyPlayer(active,en,foreground) { watching=false }
        return
    }
    BackHandler { leave() }
    LaunchedEffect(sky.busy, hubble.busy, watching) {
        if (watching || sky.busy || hubble.busy) return@LaunchedEffect
        (requesters[selection] ?: requesters.values.firstOrNull() ?: fallback).requestFocus()
    }
    Box(Modifier.fillMaxSize()) {
        NebulaBackdrop(p.poster)
        Row(Modifier.fillMaxSize().padding(horizontal=42.dp,vertical=24.dp),
            horizontalArrangement=Arrangement.spacedBy(30.dp)) {
            Column(Modifier.weight(1f).fillMaxHeight()) {
                Text(p.name.get(en),color=light,fontSize=24.sp)
                Text(dateLabel(p.date,en),color=quiet,fontSize=15.sp)
                Spacer(Modifier.height(12.dp))
                val context=LocalContext.current
                val poster=remember(context,p.poster) { ImageRequest.Builder(context).data(p.poster)
                    .transformations(LandscapePhoto).build() }
                AsyncImage(poster,null,Modifier.weight(1f).fillMaxWidth())
                Text(active?.credit.orEmpty(),color=quiet,fontSize=13.sp,maxLines=3,overflow=TextOverflow.Ellipsis)
            }
            Column(Modifier.weight(1.7f)) {
                Text(if(en) "Choose a journey" else "Kies een reis",color=light,fontSize=25.sp)
                Spacer(Modifier.height(10.dp))
                Column(Modifier.weight(1f).verticalScroll(scroll),verticalArrangement=Arrangement.spacedBy(5.dp)) {
                    for (trip in list) {
                        if (trip==hubble.items.firstOrNull()) Text("Hubble", color=coral,fontSize=17.sp)
                        Action(trip.name.get(en),Modifier.fillMaxWidth().focusRequester(requesters.getValue(trip.id))
                            .onFocusChanged { if(it.isFocused) selection=trip.id },icon=R.drawable.ic_route) {
                            selection=trip.id;watching=true
                        }
                    }
                    if(sky.busy || hubble.busy) Text(if(en) "Loading destinations…" else "Bestemmingen laden…",color=quiet)
                    if(sky.error || hubble.error) Action(if(en) "Retry destinations" else "Bestemmingen opnieuw laden") { attempt++ }
                    if(!sky.busy && !hubble.busy && list.isEmpty() && !sky.error && !hubble.error)
                        Text(if(en) "No journeys for this capture" else "Geen reizen voor deze opname",color=quiet)
                }
                Spacer(Modifier.height(6.dp))
                Action(if(en) "Back to capture" else "Terug naar opname",Modifier.focusRequester(fallback),icon=R.drawable.ic_back,run=leave)
            }
        }
    }
}

@Composable private fun JourneyPlayer(trip: Trip,en:Boolean,foreground:Boolean,leave:()->Unit) {
    var playing by rememberSaveable(trip.id) { mutableStateOf(true) }
    var hint by remember(trip.id) { mutableStateOf(true) }
    var failed by remember(trip.id) { mutableStateOf(false) }
    val focus=remember { FocusRequester() }
    BackHandler { leave() }
    LaunchedEffect(trip.id,failed) { if(failed) return@LaunchedEffect; focus.requestFocus();delay(2500);hint=false }
    Box(Modifier.fillMaxSize().background(androidx.compose.ui.graphics.Color.Black)
        .focusRequester(focus).onPreviewKeyEvent { event ->
            val ev=event.nativeKeyEvent
            if(!failed && ev.keyCode in listOf(KeyEvent.KEYCODE_DPAD_CENTER,KeyEvent.KEYCODE_ENTER,KeyEvent.KEYCODE_NUMPAD_ENTER,
                    KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE,KeyEvent.KEYCODE_MEDIA_PLAY,KeyEvent.KEYCODE_MEDIA_PAUSE)) {
                if(ev.action==KeyEvent.ACTION_UP) playing=when(ev.keyCode) {
                    KeyEvent.KEYCODE_MEDIA_PLAY -> true
                    KeyEvent.KEYCODE_MEDIA_PAUSE -> false
                    else -> !playing
                }
                true
            } else false
        }.focusable(),contentAlignment=Alignment.Center) {
        Movie(trip.url,playing,foreground,false,en) { failed=it }
        if(!failed && (hint || !playing)) Text(trip.name.get(en)+"   ·   "+(if(playing) (if(en) "OK: pause" else "OK: pauze")
            else (if(en) "OK: resume" else "OK: verder")),Modifier.align(Alignment.BottomStart).padding(28.dp)
            .background(ink.copy(alpha=.9f)).padding(8.dp),color=light,fontSize=16.sp)
    }
}
