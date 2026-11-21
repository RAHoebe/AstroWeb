package nl.ronamersfoort.astroweb.tv

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.core.content.FileProvider
import androidx.tv.material3.Text
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import java.io.File

class UpdateFileProvider : FileProvider()

@Suppress("DEPRECATION")
@Composable
internal fun UpdatePrompt(foreground: Boolean, en: Boolean) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var checked by rememberSaveable { mutableStateOf(false) }
    var update by rememberSaveable { mutableStateOf<TvUpdate?>(null) }
    var downloadedPath by rememberSaveable { mutableStateOf<String?>(null) }
    var waitingForSettings by rememberSaveable { mutableStateOf(false) }
    var problem by rememberSaveable { mutableStateOf<String?>(null) }
    var download by remember { mutableStateOf<Job?>(null) }

    val installer = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        downloadedPath?.let { File(it).delete() }
        downloadedPath = null
    }

    fun install(release: TvUpdate) {
        download = scope.launch {
            try {
                val file = downloadTvUpdate(context, release)
                downloadedPath = file.path
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.updates", file)
                installer.launch(Intent(Intent.ACTION_INSTALL_PACKAGE, uri)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    .putExtra(Intent.EXTRA_RETURN_RESULT, true))
                update = null
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                downloadedPath?.let { File(it).delete() }
                downloadedPath = null
                problem = "download"
            } finally {
                download = null
            }
        }
    }

    val settings = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        waitingForSettings = false
        val release = update
        if (release != null && context.packageManager.canRequestPackageInstalls()) install(release)
        else problem = "permission"
    }

    LaunchedEffect(Unit) {
        if (!checked) {
            try {
                update = findTvUpdate()
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // A TV can open the local collection while GitHub is unreachable.
            }
            checked = true
        }
    }

    val release = update
    if (!foreground || waitingForSettings || release == null) return
    val downloading = download != null
    val focus = remember(downloading) { FocusRequester() }
    fun dismiss() {
        download?.cancel()
        update = null
    }

    Dialog(onDismissRequest = ::dismiss) {
        val frame = RoundedCornerShape(14.dp)
        Column(Modifier.width(420.dp).background(ink, frame).border(1.dp, copper, frame).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text(if (en) "AstroWeb TV update" else "Update voor AstroWeb TV", color = light, fontSize = 23.sp)
            Text(when {
                downloading -> if (en) "Downloading version ${release.version}…" else "Versie ${release.version} downloaden…"
                problem == "permission" -> if (en) "Allow AstroWeb TV to install apps in Google TV settings to continue."
                    else "Sta AstroWeb TV toe apps te installeren in de Google TV-instellingen om verder te gaan."
                problem != null -> if (en) "The update could not be downloaded, verified or opened. Try again."
                    else "De update kon niet worden gedownload, gecontroleerd of geopend. Probeer opnieuw."
                en -> "Version ${release.version} is available on GitHub. Install it now?"
                else -> "Versie ${release.version} staat op GitHub. Wil je die nu installeren?"
            }, color = quiet, fontSize = 16.sp)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                val cancel = if (downloading) (if (en) "Cancel" else "Annuleren") else "Later"
                Action(cancel, Modifier.focusRequester(focus), run = ::dismiss)
                if (!downloading) Action(if (en) "Update" else "Bijwerken") {
                    problem = null
                    if (context.packageManager.canRequestPackageInstalls()) {
                        install(release)
                    } else {
                        try {
                            waitingForSettings = true
                            settings.launch(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                Uri.fromParts("package", context.packageName, null)))
                        } catch (_: Exception) {
                            waitingForSettings = false
                            problem = "permission"
                        }
                    }
                }
            }
        }
        LaunchedEffect(focus) { focus.requestFocus() }
    }
}
