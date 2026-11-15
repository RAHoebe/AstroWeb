package nl.ronamersfoort.astroweb.tv

import android.graphics.Bitmap
import android.graphics.Matrix
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.layout
import androidx.compose.ui.unit.Constraints
import coil.size.Size
import coil.transform.Transformation

// Studio rotates landscape originals clockwise for the portrait film. Rotate
// tall media the other way on TV so that M31's movie matches its original.
object LandscapePhoto : Transformation {
    override val cacheKey = "astroweb.tv.landscape.ccw"
    override suspend fun transform(input: Bitmap, size: Size): Bitmap {
        if (input.width >= input.height) return input
        val rotation = Matrix().apply { setRotate(-90f) }
        return Bitmap.createBitmap(input, 0, 0, input.width, input.height, rotation, true)
    }
}

fun Modifier.quarterTurns(turns: Int): Modifier = if (turns%4==0) this else layout { measurable, limits ->
    val w = limits.maxWidth
    val h = limits.maxHeight
    val swap=turns%2!=0
    val layer = measurable.measure(if(swap) Constraints.fixed(h,w) else Constraints.fixed(w,h))
    layout(w, h) {
        layer.placeWithLayer((w-layer.width)/2,(h-layer.height)/2) { rotationZ = turns*90f }
    }
}
