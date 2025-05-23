import os
import cv2
from flask import Flask, request, redirect, url_for, render_template, jsonify
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
                
                detected_candles.append({
                    'x': px, 'y': py, 'width': pw, 'height': ph, # Store processed image coordinates
                    'color_label': color_label
                })
    return detected_candles

def identify_simple_patterns(detected_candles, processed_image_height):
    """
    Identifies simple K-line patterns ("Big Yang Line", "Big Yin Line")
    from a list of detected candles.

    Args:
        detected_candles (list): A list of candle dictionaries, each produced by
                                 `detect_k_line_candles`.
        processed_image_height (int): The height of the processed image, used for
                                      relative size comparisons.

    Returns:
        list: A list of dictionaries, where each dictionary describes an
              identified pattern (pattern_name, description, candles_involved).
    """
    patterns = []
    # Threshold for a "big" candle body, relative to the processed image height (e.g., 5% of image height)
    big_candle_threshold = processed_image_height * 0.05

    for candle in detected_candles:
        candle_height = candle['height'] # Height of the candle in the processed image
        pattern_info = None

        # Identify Big Yang Line (strong bullish)
        if candle['color_label'] == 'up_candle' and candle_height > big_candle_threshold:
            pattern_info = {
                "pattern_name": "Big Yang Line",
                "description": "A strong bullish candle indicating buying pressure. The body is long and green (or white).",
                "candles_involved": [{ # List of candles forming this pattern (here, just one)
                    'x': candle['x'], 'y': candle['y'], 
                    'width': candle['width'], 'height': candle['height'],
                    'color_label': candle['color_label']
                }]
            }
        # Identify Big Yin Line (strong bearish)
        elif candle['color_label'] == 'down_candle' and candle_height > big_candle_threshold:
            pattern_info = {
                "pattern_name": "Big Yin Line",
                "description": "A strong bearish candle indicating selling pressure. The body is long and red (or black).",
                "candles_involved": [{
                    'x': candle['x'], 'y': candle['y'], 
                    'width': candle['width'], 'height': candle['height'],
                    'color_label': candle['color_label']
                }]
            }
        
        if pattern_info:
            patterns.append(pattern_info)
            
    return patterns

@app.route('/', methods=['GET'])
def upload_form():
    """
    Serves the HTML page with the file upload form.
    This route is for basic testing and demonstration via a web browser.
    """
    return render_template('upload.html')

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
        identified_patterns = identify_simple_patterns(detected_candles, processed_h)
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
