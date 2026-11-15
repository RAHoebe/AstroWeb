package nl.ronamersfoort.astroweb.tv

import android.os.Bundle
import android.view.View
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.*
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.*
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import kotlinx.coroutines.CancellationException

internal fun dateLabel(date: String, en: Boolean): String = try {
    java.time.LocalDate.parse(date).format(java.time.format.DateTimeFormatter.ofPattern(
        "d MMM yyyy", if (en) java.util.Locale.ENGLISH else java.util.Locale.forLanguageTag("nl-NL")))
} catch (_: java.time.DateTimeException) { "" }

class MainActivity : ComponentActivity() {
    private val foreground = mutableStateOf(false)
    override fun onResume() { super.onResume(); foreground.value = true }
    override fun onPause() { foreground.value = false; super.onPause() }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        setContent { MaterialTheme { App(foreground.value) } }
    }
}

@Composable internal fun Action(label: String, modifier: Modifier = Modifier, selected: Boolean = false, icon:Int? = null, run: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    val shape=RoundedCornerShape(7.dp)
    val fg=if(focused) ink else light
    Row(modifier.onFocusChanged { focused=it.isFocused }.clip(shape)
        .background(if(focused) coral else if(selected) copper else surface.copy(alpha=.94f))
        .border(if(focused) 1.5.dp else 1.dp,if(focused) light else copper.copy(alpha=.62f),shape)
        .clickable(onClick=run).heightIn(min=29.dp).padding(horizontal=9.dp,vertical=4.dp),
        verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.Center) {
        if(icon!=null) {
            Glyph(icon,if(focused) ink else quiet,14.dp)
            Spacer(Modifier.width(5.dp))
        }
        Text(label,color=fg,fontSize=13.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
    }
}

@Composable private fun App(foreground: Boolean) {
    val prefs = LocalContext.current.getSharedPreferences("viewing", 0)
    var en by remember { mutableStateOf(prefs.getBoolean("english", false)) }
    var selected by rememberSaveable { mutableStateOf("") }
    var opened by rememberSaveable { mutableStateOf<String?>(null) }
    var survey by rememberSaveable { mutableStateOf<String?>(null) }
    var lastSurvey by rememberSaveable { mutableStateOf<String?>(null) }
    var retry by remember { mutableIntStateOf(0) }
    var photos by remember { mutableStateOf<List<Photo>?>(null) }
    var failed by remember { mutableStateOf(false) }
    LaunchedEffect(retry,foreground,opened,survey) {
        if (!foreground || opened != null || survey != null) return@LaunchedEffect
        while (true) {
            try { photos=gallery(); failed=false }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { failed=photos.isNullOrEmpty() }
            kotlinx.coroutines.delay(60_000)
        }
    }
    Box(Modifier.fillMaxSize().background(ink)) {
        val list = photos
        val current = opened
        val mode=survey
        when {
            mode != null -> RemoteCanvas("collection-tv.html",selected,mode,en) { lastSurvey=mode;survey=null }
            current != null -> key(current) { Viewer(current, en, foreground) { opened = null } }
            failed || list?.isEmpty() == true -> {
                val focus = remember { FocusRequester() }
                Column(Modifier.align(Alignment.Center), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(if (en) "Collection unavailable" else "Collectie niet beschikbaar", color = light)
                    Spacer(Modifier.height(16.dp))
                    Action(if (en) "Try again" else "Opnieuw proberen", Modifier.focusRequester(focus)) { retry++ }
                }
                LaunchedEffect(Unit) { focus.requestFocus() }
            }
            list == null -> Text(if (en) "Loading gallery…" else "Galerij laden…", Modifier.align(Alignment.Center), color = light)
            else -> Gallery(list, selected, en, lastSurvey, { selected = it }, { lastSurvey=null; opened = it }, { survey=it }) {
                en = !en; prefs.edit().putBoolean("english", en).apply()
            }
        }
    }
}

@Composable private fun Gallery(photos: List<Photo>, selected: String, en: Boolean, lastSurvey: String?, select: (String)->Unit,
                                open: (String)->Unit, openSurvey: (String)->Unit, toggleLanguage: ()->Unit) {
    val current = photos.find { it.id == selected } ?: photos.first()
    val ids=remember(photos) { photos.map { it.id } }
    val focus = remember(ids) { ids.associateWith { FocusRequester() } }
    val rail=rememberLazyListState(initialFirstVisibleItemIndex=photos.indexOf(current))
    val atlasFocus=remember { FocusRequester() }
    val panoramaFocus=remember { FocusRequester() }
    var initialFocus by remember { mutableStateOf(true) }
    val ready=androidx.compose.ui.platform.LocalWindowInfo.current.isWindowFocused
    val inputMode=androidx.compose.ui.platform.LocalInputModeManager.current
    LaunchedEffect(ids,ready) {
        if(!ready)return@LaunchedEffect
        if (initialFocus || selected !in ids) {
            inputMode.requestInputMode(androidx.compose.ui.input.InputMode.Keyboard)
            rail.scrollToItem(photos.indexOf(current))
            withFrameNanos { }
            val target=when {
                initialFocus && lastSurvey=="atlas" -> atlasFocus
                initialFocus && lastSurvey=="panorama" -> panoramaFocus
                else -> focus.getValue(current.id)
            }
            initialFocus=!target.requestFocus()
        }
    }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val posterHeight = maxHeight * .46f
        val backdrop=remember(photos) { photos.firstOrNull { it.catalog=="IC_1396" }?.poster
            ?: photos.firstOrNull { it.catalog=="NGC_7000" }?.poster }
        NebulaBackdrop(backdrop ?: current.poster)
        Column(Modifier.fillMaxSize().padding(horizontal = maxWidth*.05f, vertical = maxHeight*.055f)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Glyph(R.drawable.ic_star,coral,22.dp)
                Spacer(Modifier.width(7.dp))
                Text("AstroWeb", color = light, fontWeight = FontWeight.SemiBold, fontSize = 22.sp)
                Spacer(Modifier.width(14.dp))
                Text((if (en) "Gallery" else "Galerij")+"   "+(photos.indexOf(current)+1)+" / "+photos.size, color = quiet, fontSize = 17.sp)
                Spacer(Modifier.weight(1f))
                Action(if(en) "Sky atlas" else "Hemelatlas",Modifier.focusRequester(atlasFocus),icon=R.drawable.ic_atlas) { openSurvey("atlas") }
                Spacer(Modifier.width(8.dp))
                Action(if(en) "Night panorama" else "Nachtpanorama",Modifier.focusRequester(panoramaFocus),icon=R.drawable.ic_panorama) { openSurvey("panorama") }
                Spacer(Modifier.width(8.dp))
                Action(if (en) "NL" else "EN", icon=R.drawable.ic_language, run = toggleLanguage)
            }
            Row(Modifier.fillMaxWidth().weight(1f), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Column(Modifier.weight(1f).padding(end=6.dp)) {
                    Text(current.catalog.replace('_',' '), color = coral, fontSize = 16.sp, letterSpacing = 2.sp)
                    Spacer(Modifier.height(8.dp))
                    Text(current.name.get(en), color = light, fontSize = 32.sp, lineHeight = 36.sp,
                         maxLines = 3, overflow = TextOverflow.Ellipsis)
                    Spacer(Modifier.height(12.dp))
                    Text(current.summary.get(en), color = quiet, fontSize = 16.sp, lineHeight = 21.sp,
                         maxLines = 5, overflow = TextOverflow.Ellipsis)
                    Spacer(Modifier.height(12.dp))
                    Text(dateLabel(current.date,en), color = coral, fontSize = 14.sp)
                }
                LazyRow(Modifier.weight(1.45f),state=rail,horizontalArrangement=Arrangement.spacedBy(14.dp)) {
                    items(photos,key={ it.id }) { photo ->
                        var active by remember(photo.id) { mutableStateOf(false) }
                        val frame = RoundedCornerShape(10.dp)
                        Column(Modifier.width(posterHeight*.58f)) {
                            Box(Modifier.fillMaxWidth().height(posterHeight).focusRequester(focus.getValue(photo.id))
                                .onFocusChanged { active = it.isFocused; if (active) select(photo.id) }
                                .clip(frame).background(Color(0xff150f13)).border(if (active) 3.dp else 1.dp,
                                    if (active) coral else Color(0xff754f50), frame).clickable { open(photo.id) }
                                .padding(4.dp)) {
                                AsyncImage(photo.poster, photo.name.get(en), Modifier.fillMaxSize().clip(frame),
                                    contentScale = ContentScale.Fit)
                            }
                            Spacer(Modifier.height(7.dp))
                            Text(photo.catalog.replace('_',' '), color = if (active) coral else quiet, fontSize = 14.sp)
                        }
                    }
                }
            }
            Text(if (en) "← →   Choose an object     ·     OK   Open" else "← →   Kies een object     ·     OK   Openen",
                 color=quiet, fontSize=14.sp)
        }
    }
}
