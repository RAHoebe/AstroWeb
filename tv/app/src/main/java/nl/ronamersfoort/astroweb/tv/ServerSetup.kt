package nl.ronamersfoort.astroweb.tv

import android.app.AlertDialog
import android.text.InputType
import android.widget.EditText
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.*
import androidx.tv.material3.Text
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.URI
import java.net.URL
import java.net.HttpURLConnection

@Composable internal fun ServerSetup(previous:String,en:Boolean,onConnect:(String)->Unit) {
    val context=LocalContext.current
    val scope=rememberCoroutineScope()
    var address by rememberSaveable { mutableStateOf(previous.ifBlank { if(BuildConfig.LAN_ONLY) "http://astroweb.home.arpa:8090" else "" }) }
    var status by remember { mutableStateOf("") }
    var checking by remember { mutableStateOf(false) }
    val focus=remember { FocusRequester() }
    fun edit() {
        if(checking)return
        val field=EditText(context).apply {
            inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            hint=if(BuildConfig.LAN_ONLY) "http://astroweb.home.arpa:8090" else "https://astro.example.org";setSingleLine();setText(address);setSelection(text.length)
        }
        AlertDialog.Builder(context).setTitle(if(en) "AstroWeb server" else "AstroWeb-server")
            .setView(field).setNegativeButton(android.R.string.cancel,null)
            .setPositiveButton(android.R.string.ok){ _,_ -> address=field.text.toString().trim();status="" }.show()
    }
    fun connect(){
        if(checking)return
        val typed=address.trim()
        val fullAddress=if ("://" in typed) typed else (if(BuildConfig.LAN_ONLY) "http://" else "https://")+typed
        val uri=runCatching { URI(fullAddress) }.getOrNull()
        val validTransport = if (BuildConfig.LAN_ONLY) {
            uri?.scheme == "http" && uri.host in setOf("astroweb.home.arpa","192.168.1.50","localhost")
        } else uri?.scheme == "https"
        if(uri==null || !validTransport || uri.host==null || uri.rawUserInfo!=null ||
            uri.rawPath.orEmpty() !in listOf("","/") || uri.query!=null || uri.fragment!=null) {
            status=if(BuildConfig.LAN_ONLY) "http://astroweb.home.arpa:8090" else if(en) "Enter an HTTPS server address." else "Vul een HTTPS-serveradres in.";return
        }
        val origin=fullAddress.trimEnd('/')
        checking=true;status=if(en) "Connecting…" else "Verbinden…"
        scope.launch {
            try {
                withContext(Dispatchers.IO) {
                    val c=URL(origin+"/api/health").openConnection() as HttpURLConnection
                    c.instanceFollowRedirects=false
                    c.connectTimeout=7000;c.readTimeout=7000
                    try { val h=c.inputStream.bufferedReader().use { JSONObject(it.readText()) };check(h.optBoolean("ok") && h.has("encoder") && h.has("version")) }
                    finally { c.disconnect() }
                }
                onConnect(origin)
            } catch(e:CancellationException){throw e}
            catch(_:Exception){status=if(en) "Could not reach AstroWeb. Check the address and HTTPS certificate." else "AstroWeb is niet bereikbaar. Controleer het adres en HTTPS-certificaat."}
            finally {checking=false}
        }
    }
    Column(Modifier.fillMaxSize().background(ink).padding(44.dp),verticalArrangement=Arrangement.Center) {
        Text(if(en) "Connect your collection" else "Verbind je collectie",color=light,fontSize=30.sp)
        Spacer(Modifier.height(12.dp))
        Action(address.ifBlank { if(en) "Enter server address" else "Serveradres invullen" },Modifier.focusRequester(focus)) { edit() }
        Spacer(Modifier.height(9.dp));Action(if(en) "Connect" else "Verbinden") { connect() }
        if(status.isNotBlank()){ Spacer(Modifier.height(8.dp));Text(status,color=quiet,fontSize=15.sp) }
    }
    LaunchedEffect(Unit){focus.requestFocus()}
}
