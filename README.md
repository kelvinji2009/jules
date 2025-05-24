# K-Line Technical Analysis Master - Phase 2

## Description
This project is a K-Line (candlestick chart) technical analysis tool. It allows users to upload K-line chart images via a web interface or API. The backend performs image pre-processing, detailed candle feature extraction (including bodies and wicks/shadows), identifies a range of single and two-candle patterns, and returns a structured JSON response. Phase 2 introduces a user-friendly web interface, more advanced pattern recognition, and more detailed candle analysis.

## Current Features (Phase 2)
*   **Web Interface:** A simple web page (`/`) for easy image upload and interactive display of analysis results, including the processed image.
*   **Image Upload:** Supports JPG, PNG, and GIF image formats via the web interface and the `/upload` API endpoint.
*   **Image Pre-processing:**
    *   Converts the image to grayscale.
    *   Applies Gaussian blur for noise reduction.
    *   Resizes the image to a standard width (1000px) while maintaining aspect ratio.
*   **Detailed Candle Feature Extraction:**
    *   Identifies potential candlestick bodies using contour detection.
    *   Detects **upper and lower wicks (shadows)** for each candle.
    *   Calculates body dimensions (`body_x`, `body_y`, `body_w`, `body_h`), wick end-points (`wick_high_y`, `wick_low_y`), and shadow lengths.
*   **Color Analysis:** Determines if detected candles are 'up_candle' (typically green/white), 'down_candle' (typically red/black), or 'indeterminate' by analyzing the color of the corresponding body region in the original uploaded image.
*   **Comprehensive Pattern Identification:**
    *   **Single K-line Patterns:**
        *   "Big Yang Line": A long bullish candle.
        *   "Big Yin Line": A long bearish candle.
        *   "Doji": Small body, indicating indecision.
        *   "Hammer": Bullish reversal pattern (small body, long lower shadow, short upper shadow).
        *   "Hanging Man": Bearish reversal pattern with Hammer shape.
        *   "Inverted Hammer": Bullish reversal pattern (small body, long upper shadow, short lower shadow).
        *   "Shooting Star": Bearish reversal pattern with Inverted Hammer shape.
    *   **Two-Candle Patterns:**
        *   "Bullish Engulfing": A smaller bearish candle engulfed by a larger bullish candle.
        *   "Bearish Engulfing": A smaller bullish candle engulfed by a larger bearish candle.
        *   "Tweezer Top": Two consecutive candles with nearly identical highs.
        *   "Tweezer Bottom": Two consecutive candles with nearly identical lows.
*   **Structured JSON API Response:** The `/upload` endpoint returns detailed analysis including original and processed image information, detected candle count, a list of identified patterns with involved candle details, and a disclaimer.
*   **Disclaimer:** Includes a disclaimer in the API response and this README.

## Web Interface Usage
1.  **Navigate to the application's root URL** in your web browser (typically `http://127.0.0.1:5000/`).
2.  **Select an image file** (JPG, PNG, GIF) using the "Choose File" or similar input field.
3.  **Click the "Analyze Image" button.**
4.  A loading spinner will appear while the image is processed.
5.  Once complete, the page will display:
    *   The **processed version of your uploaded image**.
    *   A list of **identified K-line patterns**, including their names, descriptions, and details of the candles involved.
    *   The **total count of potential candles** detected.
    *   Any **errors** encountered during processing.
    *   The standard **disclaimer**.

## API Endpoint

### `/upload`
*   **Method:** `POST`
*   **Description:** Uploads a K-line chart image for analysis.
*   **Request Body:** `multipart/form-data`
    *   The form must contain a file input field named `file`.
*   **Example Usage (curl):**
    ```bash
    curl -X POST -F "file=@/path/to/your/kline_chart.jpg" http://127.0.0.1:5000/upload
    ```
*   **JSON Response Structure (Success Example):**
    ```json
    {
        "filename": "my_chart.jpg",
        "processed_filename": "my_chart_processed.jpg",
        "image_dimensions": {
            "original": {"width": 1920, "height": 1080},
            "processed": {"width": 1000, "height": 562}
        },
        "detected_candles_count": 25, // Example count
        "identified_patterns": [
            {
                "pattern_name": "Bullish Engulfing",
                "description": "A potential bullish reversal signal. A smaller bearish candle is engulfed by a larger bullish candle.",
                "candles_involved": [
                    { 
                        "body_x": 100, "body_y": 200, "body_w": 10, "body_h": 30,
                        "wick_high_y": 195, "wick_low_y": 235,
                        "upper_shadow_length": 5, "lower_shadow_length": 5,
                        "color_label": "down_candle"
                    },
                    {
                        "body_x": 115, "body_y": 190, "body_w": 12, "body_h": 50,
                        "wick_high_y": 185, "wick_low_y": 245,
                        "upper_shadow_length": 5, "lower_shadow_length": 5,
                        "color_label": "up_candle"
                    }
                ]
            },
            {
                "pattern_name": "Doji",
                "description": "Indecision in the market. Open and close prices are very close, resulting in a small body. Color is less significant.",
                "candles_involved": [
                     {
                        "body_x": 150, "body_y": 180, "body_w": 2, "body_h": 2,
                        "wick_high_y": 170, "wick_low_y": 190,
                        "upper_shadow_length": 10, "lower_shadow_length": 8,
                        "color_label": "indeterminate_gray"
                    }
                ]
            }
            // ... other patterns like "Hammer", "Tweezer Top", etc.
        ],
        "disclaimer": "The analysis and any recommendations provided by this application are for educational and informational purposes only...",
        "errors": []
    }
    ```
*   **JSON Response Structure (Error Example):**
    ```json
    {
        "filename": "my_chart.txt", // Example of a disallowed file
        "processed_filename": null,
        "image_dimensions": {
            "original": {"width": null, "height": null},
            "processed": {"width": null, "height": null}
        },
        "detected_candles_count": 0,
        "identified_patterns": [],
        "disclaimer": "The analysis and any recommendations provided by this application are for educational and informational purposes only...",
        "errors": ["File type 'txt' not allowed."]
    }
    ```

## Setup and Running the Application

### Dependencies
*   Python 3 (3.7 or higher recommended)
*   Flask
*   OpenCV-Python (`opencv-python`)

### Setup Steps
1.  **Clone the repository (if applicable) or download the `app.py` file and the `templates` directory.**
2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install Flask opencv-python
    ```
4.  **Ensure the `uploads` directory exists** in the same directory as `app.py`. If not, create it:
    ```bash
    mkdir uploads
    ```
5.  **Run the Flask application:**
    Navigate to the directory containing `app.py`.
    ```bash
    python app.py
    ```
    Alternatively, you can use:
    ```bash
    flask run
    ```
    The application will typically be available at `http://127.0.0.1:5000/`.

## Important Note/Disclaimer
The analysis and any recommendations provided by this application are for educational and informational purposes only and should not be considered financial or investment advice. Trading and investing in financial markets involve substantial risk of loss. You are solely responsible for your own investment decisions. Past performance is not indicative of future results. Use this application at your own risk.
