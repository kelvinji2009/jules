# K-Line Technical Analysis Master - Phase 1

## Description
This project is the first phase of a K-Line (candlestick chart) technical analysis tool. In this phase, the application allows users to upload K-line chart images. The backend then performs basic image pre-processing, attempts to detect candlestick bodies, identifies simple patterns like "Big Yang Line" and "Big Yin Line", and returns a structured JSON response with the analysis.

## Current Features (Phase 1)
*   **Image Upload:** Supports JPG, PNG, and GIF image formats.
*   **Image Pre-processing:** Converts the image to grayscale, applies Gaussian blur for noise reduction, and resizes the image to a standard width while maintaining aspect ratio.
*   **Basic Candle Detection:** Identifies potential candlestick bodies using contour detection on the processed image.
*   **Color Analysis:** Determines if detected candles are 'up_candle' (typically green/white) or 'down_candle' (typically red/black) by analyzing the color of the corresponding region in the original uploaded image.
*   **Simple Pattern Identification:** Currently identifies:
    *   "Big Yang Line": A long bullish candle.
    *   "Big Yin Line": A long bearish candle.
*   **Structured JSON API Response:** Returns detailed analysis including original and processed image information, detected candle count, identified patterns, and a disclaimer.
*   **Disclaimer:** Includes a disclaimer in the API response and in this README.

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
        "detected_candles_count": 15,
        "identified_patterns": [
            {
                "pattern_name": "Big Yang Line",
                "description": "A strong bullish candle indicating buying pressure. The body is long and green (or white).",
                "candles_involved": [{"x": 100, "y": 200, "width": 20, "height": 80, "color_label": "up_candle"}]
            }
            // ... other patterns
        ],
        "disclaimer": "The analysis and any recommendations provided by this application are for educational and informational purposes only...",
        "errors": []
    }
    ```
*   **JSON Response Structure (Error Example):**
    ```json
    {
        "filename": "my_chart.gif",
        "processed_filename": null,
        "image_dimensions": {
            "original": {"width": null, "height": null},
            "processed": {"width": null, "height": null}
        },
        "detected_candles_count": 0,
        "identified_patterns": [],
        "disclaimer": "The analysis and any recommendations provided by this application are for educational and informational purposes only...",
        "errors": ["File type 'gif' not allowed."]
    }
    ```

## Setup and Running the Application

### Dependencies
*   Python 3 (3.7 or higher recommended)
*   Flask
*   OpenCV-Python (`opencv-python`)

### Setup Steps
1.  **Clone the repository (if applicable) or download the files.**
2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install Flask opencv-python
    ```
4.  **Run the Flask application:**
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
