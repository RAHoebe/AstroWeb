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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.font.FontWeight
import androidx.tv.material3.LocalTextStyle
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
    private var spoken by mutableStateOf<Spoken?>(null)
    private val microphone=registerForActivityResult(androidx.activity.result.contract.ActivityResultContracts.StartActivityForResult()) { result ->
        if(result.resultCode==RESULT_OK)result.data?.getStringArrayListExtra(android.speech.RecognizerIntent.EXTRA_RESULTS)
            ?.firstOrNull()?.let { spoken=Spoken(it) }
    }
    private fun listen(en:Boolean) {
        val intent=android.content.Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL,android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE,if(en) "en-US" else "nl-NL")
            .putExtra(android.speech.RecognizerIntent.EXTRA_PROMPT,if(en) "Try: Play M31" else "Bijvoorbeeld: Speel M31 af")
        try { microphone.launch(intent) }
        catch (_:android.content.ActivityNotFoundException) { android.widget.Toast.makeText(this,
            if(en) "Speech recognition unavailable" else "Spraakherkenning niet beschikbaar",android.widget.Toast.LENGTH_LONG).show() }
    }
    override fun onNewIntent(intent:android.content.Intent) {
        super.onNewIntent(intent);setIntent(intent);spokenIntent(intent)?.let { spoken=it }
    }
    private val foreground = mutableStateOf(false)
    override fun onResume() { super.onResume(); foreground.value = true }
    override fun onPause() { foreground.value = false; super.onPause() }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        if(savedInstanceState==null)spoken=spokenIntent(intent)
        setContent { MaterialTheme { App(foreground.value,spoken,{ spoken=null },::listen) } }
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

@Composable private fun App(foreground:Boolean,spoken:Spoken?,handled:()->Unit,listen:(Boolean)->Unit) {
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
    val context=LocalContext.current
    var entry by rememberSaveable { mutableStateOf("film") }
    var invocation by rememberSaveable { mutableIntStateOf(0) }
    LaunchedEffect(spoken) {
        if(spoken==null)return@LaunchedEffect
        try {
            val list=photos ?: gallery().also { photos=it }
            val dest=destination(spoken.text,list,opened ?: selected.ifBlank { list.firstOrNull()?.id })
            if(dest==null){
                android.widget.Toast.makeText(context,if(en) "No matching object or command" else "Geen passend object of opdracht",android.widget.Toast.LENGTH_LONG).show()
            } else {
                opened=dest.objectId;survey=dest.view.takeIf { it=="atlas" || it=="panorama" }
                if(dest.objectId!=null)selected=dest.objectId
                lastSurvey=null;entry=dest.view;invocation++
            }
        } catch(e:CancellationException){throw e} catch(_:Exception){
            android.widget.Toast.makeText(context,if(en) "Collection unavailable" else "Collectie niet beschikbaar",android.widget.Toast.LENGTH_LONG).show()
        }
        handled()
    }
    Box(Modifier.fillMaxSize().background(ink)) {
        val list = photos
        val current = opened
        val mode=survey
        when {
            mode != null -> RemoteCanvas("collection-tv.html",selected,mode,en) { lastSurvey=mode;survey=null }
            current != null -> key(current,invocation) { Viewer(current, en, foreground,entry) { opened = null } }
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
            else -> Gallery(list, selected, en, lastSurvey, { listen(en) }, { selected = it }, { lastSurvey=null;entry="film"; opened = it }, { survey=it }) {
                en = !en; prefs.edit().putBoolean("english", en).apply()
            }
        }
    }
}

@Composable private fun Gallery(photos: List<Photo>, selected: String, en: Boolean, lastSurvey: String?, voice:()->Unit, select: (String)->Unit,
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
        val infoLimit=maxHeight*.4f
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
                Action(if(en) "Speak" else "Spreken",icon=R.drawable.ic_mic,run=voice)
                Spacer(Modifier.width(8.dp))
                Action(if(en) "Sky atlas" else "Hemelatlas",Modifier.focusRequester(atlasFocus),icon=R.drawable.ic_atlas) { openSurvey("atlas") }
                Spacer(Modifier.width(8.dp))
                Action(if(en) "Night panorama" else "Nachtpanorama",Modifier.focusRequester(panoramaFocus),icon=R.drawable.ic_panorama) { openSurvey("panorama") }
                Spacer(Modifier.width(8.dp))
                Action(if (en) "NL" else "EN", icon=R.drawable.ic_language, run = toggleLanguage)
            }
            Spacer(Modifier.height(15.dp))
            GalleryInfo(photos,current,en,infoLimit)
            Spacer(Modifier.height(10.dp))
            BoxWithConstraints(Modifier.fillMaxWidth().weight(1f),contentAlignment=Alignment.CenterStart) {
                val gap=10.dp
                val cardWidth=minOf((maxWidth-4*gap)/5*.96f,(maxHeight-41.dp).coerceAtLeast(1.dp)*.65f)
                val posterHeight=minOf(maxHeight-41.dp,cardWidth*1.62f).coerceAtLeast(1.dp)
                LazyRow(Modifier.fillMaxWidth(),state=rail,horizontalArrangement=Arrangement.spacedBy(maxOf(gap,(maxWidth-5*cardWidth)/4))) {
                    items(photos,key={ it.id }) { photo ->
                        var active by remember(photo.id) { mutableStateOf(false) }
                        val frame = RoundedCornerShape(10.dp)
                        Column(Modifier.width(cardWidth)) {
                            Box(Modifier.fillMaxWidth().height(posterHeight).focusRequester(focus.getValue(photo.id))
                                .onFocusChanged { active = it.isFocused; if (active) select(photo.id) }
                                .clip(frame).background(Color(0xff150f13)).border(if (active) 3.dp else 1.dp,
                                    if (active) coral else Color(0xff754f50), frame).clickable { open(photo.id) }
                                .padding(4.dp)) {
                                AsyncImage(photo.poster, photo.posterName(en), Modifier.fillMaxSize().clip(frame),
                                    contentScale = ContentScale.Fit)
                            }
                            Spacer(Modifier.height(7.dp))
                            Text(photo.posterName(en), color=if(active) coral else light, fontSize=14.sp, lineHeight=16.sp, minLines=2, maxLines=2, overflow=TextOverflow.Ellipsis)
                        }
                    }
                }
            }
            Text(if (en) "← →   Choose an object     ·     OK   Open" else "← →   Kies een object     ·     OK   Openen",
                 color=quiet, fontSize=14.sp)
        }
    }
}

@Composable private fun GalleryInfo(photos:List<Photo>, current:Photo, en:Boolean, available:Dp) {
    val measurer=rememberTextMeasurer()
    val density=LocalDensity.current
    val base=LocalTextStyle.current
    val meta=base.copy(fontSize=14.sp)
    val title=base.copy(fontSize=28.sp,lineHeight=31.sp)
    val body=base.copy(fontSize=16.sp,lineHeight=20.sp)
    fun details(p:Photo)=androidx.compose.ui.text.buildAnnotatedString {
        pushStyle(androidx.compose.ui.text.SpanStyle(color=coral,fontSize=15.sp,letterSpacing=1.sp))
        append(p.catalog.replace('_',' '));pop()
        append("   ");append(dateLabel(p.date,en))
    }
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val width=constraints.maxWidth
        // Measure once per collection, language and viewport, outside the focus path.
        val tallest=remember(photos,en,width,measurer,density,meta,title,body) {
            val limit=Constraints(maxWidth=width)
            fun height(text:AnnotatedString,style:TextStyle)=measurer.measure(text,style=style,constraints=limit).size.height
            val px=photos.maxOf { p ->
                height(details(p),meta)+height(AnnotatedString(p.posterName(en)),title)+
                    height(AnnotatedString(p.gallerySummary(en)),body)
            }
            with(density){px.toDp()}
        }
        // Extra-large system fonts or unusually long descriptions can scroll
        // inside the reserved space without pushing the poster row off screen.
        key(current.id) {
            Column(Modifier.fillMaxWidth().height(minOf(available,tallest)).verticalScroll(rememberScrollState())) {
                Text(details(current),style=meta,color=quiet)
                Text(current.posterName(en),style=title,color=light)
                Text(current.gallerySummary(en),style=body,color=light)
            }
        }
    }
}
