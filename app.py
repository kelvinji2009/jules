import os
import cv2
from flask import Flask, request, redirect, url_for, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# Configuration Constants
UPLOAD_FOLDER = 'uploads'  # Directory where uploaded files will be stored
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}  # Set of allowed image file extensions
STANDARD_WIDTH = 1000  # Standard width to which images will be resized during pre-processing

# Flask application setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER  # Configure Flask app with the upload folder

def allowed_file(filename):
    """
    Checks if the uploaded file has an allowed extension.

    Args:
        filename (str): The name of the file to check.

    Returns:
        bool: True if the file extension is allowed, False otherwise.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(image_path):
    """
    Loads an image, preprocesses it, and saves the processed version.
    Preprocessing steps:
    1. Load image.
    2. Convert to grayscale.
    3. Apply Gaussian blur for noise reduction.
    4. Resize to a standard width while maintaining aspect ratio.
    5. Save the processed image.

    Args:
        image_path (str): The path to the original image.

    Returns:
        tuple: (processed_filename, height, width) of the processed image,
               or None if loading fails.
               `processed_filename` is the path to the saved processed image.
    """
    # Load the image using OpenCV
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not load image at {image_path} for preprocessing.")
        return None

    # Convert to grayscale
    gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur for noise reduction (kernel size 5x5)
    blurred_image = cv2.GaussianBlur(gray_image, (5, 5), 0)

    # Resize image maintaining aspect ratio, based on STANDARD_WIDTH
    original_height, original_width = blurred_image.shape[:2]
    aspect_ratio = original_height / original_width
    new_height = int(STANDARD_WIDTH * aspect_ratio)
    resized_image = cv2.resize(blurred_image, (STANDARD_WIDTH, new_height))

    # Save the processed image, appending '_processed' to the original filename
    filename, file_extension = os.path.splitext(image_path)
    processed_filename = f"{filename}_processed{file_extension}"
    try:
        cv2.imwrite(processed_filename, resized_image)
    except Exception as e:
        print(f"Error saving processed image {processed_filename}: {e}")
        return None
        
    return processed_filename, resized_image.shape[0], resized_image.shape[1] # path, height, width

def detect_k_line_candles(original_image_path, processed_image_path, processed_img_height, processed_img_width):
    """
    Detects potential K-line candle bodies from a processed image and determines their color
    from the original image.

    Args:
        original_image_path (str): Path to the original uploaded image (for color analysis).
        processed_image_path (str): Path to the pre-processed (grayscale, resized) image.
        processed_img_height (int): Height of the processed image.
        processed_img_width (int): Width of the processed image.

    Returns:
        list: A list of dictionaries, where each dictionary represents a detected candle.
              Each candle dict contains 'x', 'y', 'width', 'height' (from processed image)
              and 'color_label' ('up_candle', 'down_candle', 'indeterminate_...').
              Returns an empty list if image loading fails.
    """
    processed_img = cv2.imread(processed_image_path, cv2.IMREAD_GRAYSCALE)
    if processed_img is None:
        print(f"Error: Could not load processed image at {processed_image_path} for candle detection.")
        return []

    original_img = cv2.imread(original_image_path)
    if original_img is None:
        print(f"Error: Could not load original image at {original_image_path} for color analysis.")
        return []
    
    original_img_height, original_img_width = original_img.shape[:2]

    # Calculate scaling factors to map coordinates from processed to original image
    scale_x = original_img_width / processed_img_width
    scale_y = original_img_height / processed_img_height

    # Apply Canny edge detection on the processed image to find edges
    # Thresholds (50, 150) are common starting points and might need tuning.
    edges = cv2.Canny(processed_img, 50, 150)

    # Find contours from the edge-detected image
    # cv2.RETR_EXTERNAL retrieves only the extreme outer contours.
    # cv2.CHAIN_APPROX_SIMPLE compresses horizontal, vertical, and diagonal segments.
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected_candles = []

    # Heuristic parameters for filtering candle shapes from the processed image.
    # These are relative to the processed image dimensions and may need tuning based on typical chart styles.
    min_candle_height_processed = processed_img_height * 0.01  # Min height: 1% of processed image height
    max_candle_height_processed = processed_img_height * 0.5   # Max height: 50% of processed image height
    min_candle_width_processed = processed_img_width * 0.005   # Min width: 0.5% of processed image width
    max_candle_width_processed = processed_img_width * 0.1    # Max width: 10% of processed image width
    min_aspect_ratio_processed = 1.5  # Min aspect ratio (height/width)
    max_aspect_ratio_processed = 15   # Max aspect ratio

    for contour in contours:
        px, py, pw, ph = cv2.boundingRect(contour) # Bounding box from processed image

        # Filter contours based on size and aspect ratio heuristics
        if ph > 0 and pw > 0: # Ensure width and height are positive
            aspect_ratio = ph / pw
            if (min_candle_height_processed <= ph <= max_candle_height_processed) and \
               (min_candle_width_processed <= pw <= max_candle_width_processed) and \
               (min_aspect_ratio_processed <= aspect_ratio <= max_aspect_ratio_processed):

                # Map contour bounding box coordinates back to the original image space
                ox = int(px * scale_x)
                oy = int(py * scale_y)
                ow = int(pw * scale_x)
                oh = int(ph * scale_y)

                # Ensure the ROI is within the bounds of the original image
                ox_end = min(ox + ow, original_img_width)
                oy_end = min(oy + oh, original_img_height)
                
                color_label = 'indeterminate_error' # Default in case ROI is invalid
                if ox_end > ox and oy_end > oy: # Check for a valid ROI area
                    roi_original = original_img[oy:oy_end, ox:ox_end] # Extract ROI from original color image
                    
                    if roi_original.size == 0:
                        color_label = 'indeterminate_color_empty_roi'
                    else:
                        # Calculate the average color (BGR) of the ROI
                        avg_color_bgr = cv2.mean(roi_original)[:3]
                        b_avg, g_avg, r_avg = avg_color_bgr

                        # Color determination logic
                        color_intensity_threshold = 20 # Minimum average intensity to be considered 'colored' (not black/very dark)
                        color_diff_factor = 1.1 # How much stronger one color channel should be than another

                        if max(b_avg, g_avg, r_avg) < color_intensity_threshold : # Check if color is very dark (near black)
                             color_label = 'indeterminate_dark'
                        elif abs(r_avg - g_avg) < 10 and abs(r_avg - b_avg) < 10 and abs(g_avg - b_avg) < 10 : # Check if color is grayscale-like
                             color_label = 'indeterminate_gray'
                        elif g_avg > r_avg * color_diff_factor and g_avg > b_avg: # Predominantly green (bullish)
                            color_label = 'up_candle'
                        elif r_avg > g_avg * color_diff_factor and r_avg > b_avg: # Predominantly red (bearish)
                            color_label = 'down_candle'
                        else: # Other mixed colors
                            color_label = 'indeterminate_mixed_color'
                else:
                    color_label = 'indeterminate_roi_out_of_bounds' # Mapped ROI was outside original image
                
                # Wick Detection Logic (on processed_img)
                wick_high_y = py
                wick_low_y = py + ph
                candle_center_x = px + pw // 2

                # Ensure candle_center_x is within image bounds
                if candle_center_x >= processed_img_width:
                    candle_center_x = processed_img_width -1
                
                # Upper Wick Scan (scan from body top upwards)
                # Consider a small horizontal window for robustness
                scan_width = max(1, pw // 8) # Scan width, e.g., 1/8 of body width
                x_start_scan = max(0, candle_center_x - scan_width // 2)
                x_end_scan = min(processed_img_width, candle_center_x + scan_width // 2 + 1)

                # Define a threshold for wick pixels (e.g., darker than a value, assuming light background)
                # This threshold is critical and may need to be adaptive or tuned.
                # For now, let's use a relatively dark threshold (e.g., < 100 for 8-bit grayscale)
                # or check if it's significantly darker than the area just above the body.
                # A simpler approach: if the body is dark, wicks are dark. If light, wicks are light.
                # This is complex. Let's use a fixed threshold for now on the grayscale image.
                wick_pixel_threshold = 150 # Pixels darker than this are potentially part of a wick line

                for y_scan in range(py - 1, -1, -1): # Scan upwards
                    is_wick_pixel_found = False
                    # Check pixels in the horizontal scan window
                    for x_s in range(x_start_scan, x_end_scan):
                        if processed_img[y_scan, x_s] < wick_pixel_threshold:
                            is_wick_pixel_found = True
                            break
                    if is_wick_pixel_found:
                        wick_high_y = y_scan
                    else: # Line broken
                        break 
                
                # Lower Wick Scan (scan from body bottom downwards)
                for y_scan in range(py + ph, processed_img_height): # Scan downwards
                    is_wick_pixel_found = False
                    for x_s in range(x_start_scan, x_end_scan):
                        if processed_img[y_scan, x_s] < wick_pixel_threshold:
                            is_wick_pixel_found = True
                            break
                    if is_wick_pixel_found:
                        wick_low_y = y_scan
                    else: # Line broken
                        break

                detected_candles.append({
                    'body_x': px, 'body_y': py, 'body_w': pw, 'body_h': ph,
                    'wick_high_y': wick_high_y,
                    'wick_low_y': wick_low_y,
                    'upper_shadow_length': py - wick_high_y,
                    'lower_shadow_length': wick_low_y - (py + ph),
                    'color_label': color_label
                })
    return detected_candles

def identify_candle_patterns(detected_candles, processed_image_height):
    """
    Identifies various single K-line patterns from a list of detected candles.
    Includes Big Yang/Yin, Doji, Hammer, Hanging Man, Inverted Hammer, Shooting Star.
    The distinction between Hammer/Hanging Man and Inv Hammer/Shooting Star is based
    on shape and color for now; trend context is not yet considered.

    Args:
        detected_candles (list): A list of candle dictionaries, each produced by
                                 `detect_k_line_candles` (must include wick info).
        processed_image_height (int): The height of the processed image, used for
                                      relative size comparisons.

    Returns:
        list: A list of dictionaries, where each dictionary describes an
              identified pattern (pattern_name, description, candles_involved).
    """
    patterns = []

    # --- Thresholds and Ratios for Pattern Recognition (Sensible Defaults - May Need Tuning) ---

    # For Big Yang/Yin: Body height relative to processed image height.
    big_candle_body_min_ratio_to_image = 0.05 

    # For Doji: Max body height relative to total candle range (high-low).
    doji_body_max_ratio_to_total_range = 0.1 

    # For Hammer & Hanging Man:
    hammer_body_max_ratio_to_total_range = 0.33  # Body is max 1/3 of total candle range.
    hammer_lower_shadow_min_ratio_to_body = 2.0  # Lower shadow at least 2x body height.
    hammer_upper_shadow_max_ratio_to_body = 1.0  # Upper shadow no more than 1x body height (relatively small).

    # For Inverted Hammer & Shooting Star:
    inv_hammer_body_max_ratio_to_total_range = 0.33 # Body is max 1/3 of total candle range.
    inv_hammer_upper_shadow_min_ratio_to_body = 2.0 # Upper shadow at least 2x body height.
    inv_hammer_lower_shadow_max_ratio_to_body = 1.0 # Lower shadow no more than 1x body height.
    
    # Minimum total range (pixels) for a candle to be considered for Doji/Hammer type patterns.
    # This helps avoid classifying noise or very small, insignificant candles.
    min_total_range_for_complex_pattern_px = processed_image_height * 0.01 # e.g. 1% of image height

    # --- Thresholds for Two-Candle Patterns ---
    # Engulfing: No specific ratio for body size, just strict engulfment.
    # Tweezer Tops/Bottoms: Max difference in highs/lows.
    # This can be a fixed pixel value or a ratio of average candle height.
    # Using a small pixel value for now, e.g., 2-3 pixels, assuming STANDAR_WIDTH is 1000px.
    # A more robust way would be relative to candle size or volatility.
    tweezer_max_diff_px = processed_image_height * 0.003 # 0.3% of image height, e.g., 3px if height is 1000px
                                                         # This is a very strict threshold.

    # Sort candles by their horizontal position ('body_x') to process them in chart order.
    # This is crucial for two-candle pattern detection.
    sorted_candles = sorted(detected_candles, key=lambda c: c['body_x'])
    
    num_candles = len(sorted_candles)

    # --- Single-Candle Pattern Identification ---
    for i in range(num_candles):
        candle = sorted_candles[i]
        body_h = candle['body_h']
        upper_shadow = candle['upper_shadow_length']
        lower_shadow = candle['lower_shadow_length']
        color = candle['color_label']
        
        total_range = body_h + upper_shadow + lower_shadow

        # --- Pattern Identification Logic ---

        # 1. Big Yang Line
        if color == 'up_candle' and body_h > (processed_image_height * big_candle_body_min_ratio_to_image):
            patterns.append({
                "pattern_name": "Big Yang Line",
                "description": "A strong bullish candle indicating buying pressure. The body is long and typically green/white.",
                "candles_involved": [candle]
            })
            continue # A Big Yang is usually not also a Doji/Hammer etc.

        # 2. Big Yin Line
        if color == 'down_candle' and body_h > (processed_image_height * big_candle_body_min_ratio_to_image):
            patterns.append({
                "pattern_name": "Big Yin Line",
                "description": "A strong bearish candle indicating selling pressure. The body is long and typically red/black.",
                "candles_involved": [candle]
            })
            continue # A Big Yin is usually not also a Doji/Hammer etc.

        # Proceed with other patterns only if the candle has a significant total range
        if total_range < min_total_range_for_complex_pattern_px and \
           not (patterns and patterns[-1]["pattern_name"] in ["Big Yang Line", "Big Yin Line"]): # Avoid skipping if Big Yang/Yin was just added
            # If a Big Yang/Yin was identified, we already 'continue'd for that candle.
            # This 'continue' is for candles that are NOT Big Yang/Yin AND are too small for other complex patterns.
            if not any(p_info["candles_involved"][0] == candle for p_info in patterns if p_info["pattern_name"] in ["Big Yang Line", "Big Yin Line"]):
                 continue


        # 3. Doji
        # Condition: Body height is very small compared to the total candle range.
        is_doji_body = (body_h / total_range) < doji_body_max_ratio_to_total_range if total_range > 0 else body_h < (processed_image_height *0.005) # very small body if no range
        if is_doji_body:
            patterns.append({
                "pattern_name": "Doji",
                "description": "Indecision in the market. Open and close prices are very close, resulting in a small body. Color is less significant.",
                "candles_involved": [candle]
            })
            # Doji is a primary classification; usually don't classify as Hammer/etc. if it's a clear Doji.
            # However, some Doji (like Dragonfly/Gravestone) can overlap with Hammer/ShootingStar shapes.
            # For now, if it's a Doji, we might skip other shape-based ones or make them less likely.
            # Let's allow other classifications for now, but this could be refined.

        # 4. Hammer / Hanging Man (shape-based first)
        is_hammer_shape_body_small = (body_h / total_range) < hammer_body_max_ratio_to_total_range if total_range > 0 else False
        is_hammer_shape_lower_shadow_long = lower_shadow >= (hammer_lower_shadow_min_ratio_to_body * body_h) if body_h > 0 else lower_shadow > (total_range * 0.6) # if body is tiny, lower shadow is most of candle
        is_hammer_shape_upper_shadow_short = upper_shadow < (hammer_upper_shadow_max_ratio_to_body * body_h) if body_h > 0 else upper_shadow < (total_range * 0.3) # if body is tiny, upper shadow is small part

        if is_hammer_shape_body_small and is_hammer_shape_lower_shadow_long and is_hammer_shape_upper_shadow_short:
            if color == 'up_candle' or color == 'indeterminate_gray' or color == 'indeterminate_mixed_color': # Typically bullish body for Hammer
                patterns.append({
                    "pattern_name": "Hammer",
                    "description": "Potential bullish reversal signal. Small body near the top, long lower shadow, very short or no upper shadow. Typically appears after a downtrend.",
                    "candles_involved": [candle]
                })
            else: # 'down_candle' or 'indeterminate_dark'
                patterns.append({
                    "pattern_name": "Hanging Man",
                    "description": "Potential bearish reversal signal if after an uptrend. Shape is like a Hammer (small body, long lower shadow, short upper shadow), but color can be bearish.",
                    "candles_involved": [candle]
                })

        # 5. Inverted Hammer / Shooting Star (shape-based first)
        is_inv_hammer_shape_body_small = (body_h / total_range) < inv_hammer_body_max_ratio_to_total_range if total_range > 0 else False
        is_inv_hammer_shape_upper_shadow_long = upper_shadow >= (inv_hammer_upper_shadow_min_ratio_to_body * body_h) if body_h > 0 else upper_shadow > (total_range * 0.6)
        is_inv_hammer_shape_lower_shadow_short = lower_shadow < (inv_hammer_lower_shadow_max_ratio_to_body * body_h) if body_h > 0 else lower_shadow < (total_range * 0.3)

        if is_inv_hammer_shape_body_small and is_inv_hammer_shape_upper_shadow_long and is_inv_hammer_shape_lower_shadow_short:
            if color == 'up_candle' or color == 'indeterminate_gray' or color == 'indeterminate_mixed_color': # Typically bullish body for Inverted Hammer
                patterns.append({
                    "pattern_name": "Inverted Hammer",
                    "description": "Potential bullish reversal signal. Small body near the bottom, long upper shadow, very short or no lower shadow. Typically appears after a downtrend.",
                    "candles_involved": [candle]
                })
            else: # 'down_candle' or 'indeterminate_dark'
                patterns.append({
                    "pattern_name": "Shooting Star",
                    "description": "Potential bearish reversal signal if after an uptrend. Shape is like an Inverted Hammer (small body, long upper shadow, short lower shadow), but color can be bearish.",
                    "candles_involved": [candle]
                })
            
    
    # --- Two-Candle Pattern Identification ---
    # Iterate up to the second to last candle to compare candle[i] with candle[i+1]
    for i in range(num_candles - 1):
        c1 = sorted_candles[i]  # First candle
        c2 = sorted_candles[i+1] # Second candle

        # 1. Bullish Engulfing
        if c1['color_label'] == 'down_candle' and c2['color_label'] == 'up_candle':
            # Second candle's body must engulf the first candle's body
            if (c2['body_y'] < c1['body_y']) and \
               ((c2['body_y'] + c2['body_h']) > (c1['body_y'] + c1['body_h'])):
                patterns.append({
                    "pattern_name": "Bullish Engulfing",
                    "description": "A potential bullish reversal signal. A smaller bearish candle is engulfed by a larger bullish candle.",
                    "candles_involved": [c1, c2]
                })

        # 2. Bearish Engulfing
        elif c1['color_label'] == 'up_candle' and c2['color_label'] == 'down_candle':
            # Second candle's body must engulf the first candle's body
            if (c2['body_y'] < c1['body_y']) and \
               ((c2['body_y'] + c2['body_h']) > (c1['body_y'] + c1['body_h'])):
                patterns.append({
                    "pattern_name": "Bearish Engulfing",
                    "description": "A potential bearish reversal signal. A smaller bullish candle is engulfed by a larger bearish candle.",
                    "candles_involved": [c1, c2]
                })
        
        # 3. Tweezer Top
        # Highs are nearly identical. Using wick_high_y which is the absolute highest point.
        # c1['wick_high_y'] is the y-coordinate of the highest point of candle 1. Lower y means higher on chart.
        if abs(c1['wick_high_y'] - c2['wick_high_y']) <= tweezer_max_diff_px:
            # Optionally, add color/trend context, e.g., c1 bullish, c2 bearish after uptrend
            patterns.append({
                "pattern_name": "Tweezer Top",
                "description": "Potential bearish reversal. Two consecutive candles with nearly identical highs.",
                "candles_involved": [c1, c2]
            })

        # 4. Tweezer Bottom
        # Lows are nearly identical. Using wick_low_y which is the absolute lowest point.
        # c1['wick_low_y'] is the y-coordinate of the lowest point of candle 1. Higher y means lower on chart.
        if abs(c1['wick_low_y'] - c2['wick_low_y']) <= tweezer_max_diff_px:
            # Optionally, add color/trend context
            patterns.append({
                "pattern_name": "Tweezer Bottom",
                "description": "Potential bullish reversal. Two consecutive candles with nearly identical lows.",
                "candles_involved": [c1, c2]
            })
            
    return patterns

@app.route('/', methods=['GET'])
def index():
    """
    Serves the main HTML page (index.html) for the application.
    """
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    Serves uploaded files from the UPLOAD_FOLDER.
    This allows the frontend to display uploaded and processed images.
    """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Handles file uploads, performs image processing and K-line analysis,
    and returns a structured JSON response.
    """
    # Initialize the response dictionary that will be converted to JSON
    response_dict = {
        "filename": None,
        "processed_filename": None,
        "image_dimensions": {
            "original": {"width": None, "height": None},
            "processed": {"width": None, "height": None}
        },
        "detected_candles_count": 0,
        "identified_patterns": [],
        "disclaimer": "The analysis and any recommendations provided by this application are for educational and informational purposes only and should not be considered financial or investment advice. Trading and investing in financial markets involve substantial risk of loss. You are solely responsible for your own investment decisions. Past performance is not indicative of future results. Use this application at your own risk.",
        "errors": []
    }

    if 'file' not in request.files:
        response_dict["errors"].append("No file part in the request.")
        return jsonify(response_dict), 400
    
    file = request.files['file']
    if file.filename == '':
        response_dict["errors"].append("No file selected for upload.")
        return jsonify(response_dict), 400

    if not allowed_file(file.filename):
        response_dict["errors"].append(f"File type '{file.filename.rsplit('.', 1)[1].lower()}' not allowed.")
        return jsonify(response_dict), 400

    filename = secure_filename(file.filename)
    response_dict["filename"] = filename
    original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        file.save(original_filepath)

        # Get original image dimensions
        original_img_for_dims = cv2.imread(original_filepath)
        if original_img_for_dims is None:
            response_dict["errors"].append("Could not read the saved original image to get dimensions.")
            # Clean up saved file if it's corrupted or unreadable by OpenCV
            if os.path.exists(original_filepath): os.remove(original_filepath)
            return jsonify(response_dict), 500
        
        orig_h, orig_w = original_img_for_dims.shape[:2]
        response_dict["image_dimensions"]["original"]["width"] = orig_w
        response_dict["image_dimensions"]["original"]["height"] = orig_h

        # Pre-process the image
        processed_data = preprocess_image(original_filepath)
        if not processed_data:
            response_dict["errors"].append("Image pre-processing failed.")
            return jsonify(response_dict), 500
        
        processed_image_path, processed_h, processed_w = processed_data
        response_dict["processed_filename"] = os.path.basename(processed_image_path)
        response_dict["image_dimensions"]["processed"]["width"] = processed_w
        response_dict["image_dimensions"]["processed"]["height"] = processed_h

        # Detect K-line candles
        detected_candles = detect_k_line_candles(original_filepath, processed_image_path, processed_h, processed_w)
        response_dict["detected_candles_count"] = len(detected_candles)
        # Storing full candle details for potential future use in response, though patterns only use some.
        # response_dict["detected_candles_details"] = detected_candles 

        # Identify patterns
        identified_patterns = identify_candle_patterns(detected_candles, processed_h) # Changed function name
        response_dict["identified_patterns"] = identified_patterns
        
        if not response_dict["errors"]: # If errors were empty until now
             return jsonify(response_dict), 200

    except Exception as e:
        print(f"An error occurred: {e}") # Log to server console
        response_dict["errors"].append(f"An unexpected error occurred during processing: {str(e)}")
        # Clean up potentially partially processed files
        if os.path.exists(original_filepath): os.remove(original_filepath)
        if 'processed_image_path' in locals() and os.path.exists(processed_image_path): os.remove(processed_image_path)
        return jsonify(response_dict), 500
    
    # Fallback if errors were added but not returned (should ideally not be reached if logic is correct)
    return jsonify(response_dict), 500


if __name__ == '__main__':
    app.run(debug=True)
