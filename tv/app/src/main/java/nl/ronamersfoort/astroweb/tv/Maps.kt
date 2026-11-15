package nl.ronamersfoort.astroweb.tv

import android.annotation.SuppressLint
import android.net.Uri
import android.view.KeyEvent
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.*
import androidx.compose.ui.viewinterop.AndroidView
import androidx.tv.material3.Text

private enum class Chart(val slug:String,val nl:String,val en:String) {
    SKY("sky","Skykaart","Sky chart"), POLAR("polar","Poolkaart","Polar chart"), GALAXY("galaxy","Melkweg","Milky Way")
}

@Composable internal fun Maps(photo: Photo,en: Boolean,foreground:Boolean,leave: ()->Unit) {
    var selected by rememberSaveable(photo.id) { mutableStateOf(Chart.SKY) }
    var full by rememberSaveable(photo.id) { mutableStateOf(false) }
    val focus=remember { FocusRequester() }
    BackHandler { if(full) full=false else leave() }
    if(full) {
        RemoteCanvas("map.html",photo.id,selected.slug,en,foreground=foreground)
        return
    }
    Box(Modifier.fillMaxSize()) {
        NebulaBackdrop(photo.poster)
        Column(Modifier.fillMaxSize().padding(horizontal=42.dp,vertical=38.dp),verticalArrangement=Arrangement.Bottom) {
            Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                Glyph(R.drawable.ic_maps,coral,19.dp)
                Text(if(en) "Maps" else "Kaarten",color=coral,fontSize=17.sp)
            }
            Spacer(Modifier.height(8.dp))
            Text(photo.name.get(en),color=light,fontSize=32.sp,lineHeight=36.sp)
            Text(dateLabel(photo.date,en),color=quiet,fontSize=15.sp)
            Spacer(Modifier.height(15.dp))
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                for(chart in Chart.entries.filter { it != Chart.GALAXY || photo.milkyWay }) {
                    val icon=when(chart) { Chart.SKY -> R.drawable.ic_sky; Chart.POLAR -> R.drawable.ic_polar; Chart.GALAXY -> R.drawable.ic_galaxy }
                    Action(if(en) chart.en else chart.nl,if(chart==selected) Modifier.focusRequester(focus) else Modifier,icon=icon) {
                        selected=chart;full=true
                    }
                }
            }
        }
    }
    LaunchedEffect(Unit) { focus.requestFocus() }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable internal fun RemoteCanvas(asset:String,id:String,mode:String,en:Boolean,foreground:Boolean=true,leave:(()->Unit)?=null) {
    val context=LocalContext.current
    val page=remember(asset,id,mode,en) {
        context.assets.open(asset).bufferedReader().use { it.readText() }
            .replace("__CAPTURE__",Uri.encode(id)).replace("__MAP__",mode).replace("__LANG__",if(en) "en" else "nl")
    }
    var web by remember { mutableStateOf<WebView?>(null) }
    val focus=remember { FocusRequester() }
    LaunchedEffect(web,foreground) {
        if(!foreground && asset=="map.html") web?.evaluateJavascript("window.mapKey?.('pause')",null)
    }
    if(leave!=null) BackHandler {
        val view=web
        if(view==null) leave() else view.evaluateJavascript("window.collectionBack?.() === true") { consumed ->
            if(consumed!="true") leave()
        }
    }
    Box(Modifier.fillMaxSize().background(ink).focusRequester(focus).onPreviewKeyEvent { key ->
        val ev=key.nativeKeyEvent
        val command=when(ev.keyCode) {
            KeyEvent.KEYCODE_DPAD_UP -> "in"
            KeyEvent.KEYCODE_DPAD_DOWN -> "out"
            KeyEvent.KEYCODE_DPAD_LEFT -> "previous"
            KeyEvent.KEYCODE_DPAD_RIGHT -> "next"
            KeyEvent.KEYCODE_DPAD_CENTER,KeyEvent.KEYCODE_ENTER,KeyEvent.KEYCODE_NUMPAD_ENTER -> if(asset=="map.html") "toggle" else "reset"
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE -> if(asset=="map.html") "toggle" else return@onPreviewKeyEvent false
            KeyEvent.KEYCODE_MEDIA_PLAY -> if(asset=="map.html") "play" else return@onPreviewKeyEvent false
            KeyEvent.KEYCODE_MEDIA_PAUSE -> if(asset=="map.html") "pause" else return@onPreviewKeyEvent false
            else -> return@onPreviewKeyEvent false
        }
        if(command=="toggle") {
            if(ev.action==KeyEvent.ACTION_UP) {
                val action=if(ev.eventTime-ev.downTime>=android.view.ViewConfiguration.getLongPressTimeout() && ev.keyCode!=KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE) "reset" else "toggle"
                web?.evaluateJavascript("window.mapKey?.('$action')",null)
            }
        } else if(ev.action==KeyEvent.ACTION_DOWN && (ev.repeatCount==0 || (command in listOf("in","out","previous","next") && ev.repeatCount%4==0)))
            web?.evaluateJavascript("window.mapKey?.('$command')",null)
        true
    }.focusable()) {
        AndroidView(factory={ ctx -> WebView(ctx).apply {
            isFocusable=false; isFocusableInTouchMode=false
            setBackgroundColor(android.graphics.Color.rgb(8,15,25))
            settings.javaScriptEnabled=true
            settings.domStorageEnabled=true
            settings.allowFileAccess=false;settings.allowContentAccess=false
            webViewClient=object:WebViewClient() {
                override fun shouldOverrideUrlLoading(view:WebView,request:WebResourceRequest)=true
            }
            loadDataWithBaseURL("$server/",page,"text/html","utf-8",null)
            web=this
        } },modifier=Modifier.fillMaxSize(),onRelease={ it.stopLoading();it.destroy();web=null })
    }
    LaunchedEffect(Unit) { focus.requestFocus() }
}
