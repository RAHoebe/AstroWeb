package nl.ronamersfoort.astroweb.tv

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.*
import coil.compose.AsyncImage
import coil.request.ImageRequest

// Dust shadows, red emission and illuminated rims from IC 1396 and NGC 7000.
internal val ink=Color(0xff180f14)
internal val surface=Color(0xff392327)
internal val copper=Color(0xff85423b)
internal val coral=Color(0xffed998a)
internal val quiet=Color(0xffdcc0b8)
internal val light=Color(0xffffefe6)

@Composable internal fun Glyph(icon:Int,tint:Color,size:Dp) {
    Image(painterResource(icon),null,Modifier.size(size),colorFilter=ColorFilter.tint(tint))
}

@Composable internal fun NebulaBackdrop(url:String?) {
    val context=LocalContext.current
    val image=remember(url,context) { ImageRequest.Builder(context).data(url)
        .transformations(LandscapePhoto).crossfade(220).build() }
    Box(Modifier.fillMaxSize().background(Brush.horizontalGradient(listOf(ink,surface,copper)))) {
        AsyncImage(image,null,Modifier.fillMaxSize(),contentScale=ContentScale.Crop)
        Box(Modifier.fillMaxSize().background(Brush.horizontalGradient(listOf(ink.copy(alpha=.86f),
            ink.copy(alpha=.48f),ink.copy(alpha=.14f)))))
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(ink.copy(alpha=.32f),
            Color.Transparent,ink.copy(alpha=.72f)))))
    }
}
