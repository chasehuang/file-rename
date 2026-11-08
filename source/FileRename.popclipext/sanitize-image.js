ObjC.import('Foundation');
ObjC.import('ImageIO');
ObjC.import('CoreGraphics');

// This helper receives only private temporary paths, never the original file.
// Decode pixels (not an embedded thumbnail), apply EXIF orientation, then encode
// a new PNG without copying source properties. Python strips ancillary chunks
// from this output as a second step before any bytes reach the network.
function run(argv) {
  try {
    if (argv.length !== 2) return 'ERROR';
    const source = $.CGImageSourceCreateWithURL($.NSURL.fileURLWithPath(argv[0]), null);
    if (!source) return 'ERROR';
    const options = $.NSMutableDictionary.alloc.init;
    const set = (key, value) => options.setObjectForKey($(value), ObjC.castRefToObject(key));
    set($.kCGImageSourceCreateThumbnailFromImageAlways, true);
    set($.kCGImageSourceCreateThumbnailWithTransform, true);
    set($.kCGImageSourceThumbnailMaxPixelSize, 1600);
    const image = $.CGImageSourceCreateThumbnailAtIndex(source, 0, options);
    if (!image) return 'ERROR';
    // Draw into a new sRGB RGBA bitmap so stripping an embedded color profile
    // does not change how the pixels should be interpreted. The cleared bitmap
    // also avoids retaining hidden source RGB data behind fully transparent areas.
    const width = $.CGImageGetWidth(image), height = $.CGImageGetHeight(image);
    if (width < 1 || height < 1 || width > 1600 || height > 1600) return 'ERROR';
    const colorSpace = $.CGColorSpaceCreateWithName($.kCGColorSpaceSRGB);
    const bitmap = $.CGBitmapContextCreate(null, width, height, 8, width * 4, colorSpace,
      $.kCGImageAlphaPremultipliedLast | $.kCGBitmapByteOrder32Big);
    if (!bitmap) return 'ERROR';
    const rect = $.CGRectMake(0, 0, width, height);
    $.CGContextClearRect(bitmap, rect);
    $.CGContextDrawImage(bitmap, rect, image);
    const cleanImage = $.CGBitmapContextCreateImage(bitmap);
    if (!cleanImage) return 'ERROR';
    const destination = $.CGImageDestinationCreateWithURL($.NSURL.fileURLWithPath(argv[1]), $('public.png'), 1, null);
    if (!destination) return 'ERROR';
    $.CGImageDestinationAddImage(destination, cleanImage, null);
    return $.CGImageDestinationFinalize(destination) ? 'OK' : 'ERROR';
  } catch (_) {
    // Never print source properties, image bytes or underlying decoder errors.
    return 'ERROR';
  }
}
