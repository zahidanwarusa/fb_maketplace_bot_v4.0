# Facebook Marketplace Automation

## Table of Contents
1. [Introduction](#introduction)
2. [Features](#features)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [Project Structure](#project-structure)
8. [Development](#development)
9. [Troubleshooting](#troubleshooting)
10. [Contributing](#contributing)
11. [License](#license)

## Introduction

Facebook Marketplace Automation is a tool designed to streamline the process of listing vehicles on Facebook Marketplace. It provides a web interface for managing listings and Chrome profiles, and automates the posting process using Selenium.

## Features

- Web-based interface for managing vehicle listings
- Integration with multiple Chrome profiles
- Automated posting to Facebook Marketplace
- Location management for different Chrome profiles
- Robust error handling and logging

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.7 or higher
- Google Chrome browser installed
- ChromeDriver compatible with your Chrome version
- Git (for cloning the repository)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/facebook-marketplace-automation.git
   cd facebook-marketplace-automation
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Download ChromeDriver:
   - Visit the [ChromeDriver downloads page](https://sites.google.com/a/chromium.org/chromedriver/downloads)
   - Download the version that matches your Chrome browser
   - Extract the executable and place it in a directory that's in your system's PATH

## Configuration

1. Create a `profile_locations.json` file in the project root (if it doesn't exist):
   ```json
   {
     "Profile 1": "New York, NY",
     "Profile 2": "Los Angeles, CA",
     "Default": "Chicago, IL"
   }
   ```

2. Ensure your `listings.csv` file is properly formatted with the following headers:
   ```
   Year,Make,Model,Mileage,Price,Body Style,Exterior Color,Interior Color,Vehicle Condition,Fuel Type,Transmission,Description,Images Path
   ```

3. Update the `chromedriver` path in `bot.py` if necessary:
   ```python
   service = Service(executable_path=r"path/to/your/chromedriver")
   ```

## Usage

1. Start the Flask application:
   ```
   python app.py
   ```

2. Open a web browser and navigate to `http://localhost:5000`

3. Use the web interface to:
   - Add new vehicle listings
   - Select Chrome profiles and set their locations
   - Choose listings to post
   - Run the automation bot

## Project Structure

```
facebook-marketplace-automation/
├── app.py              # Main Flask application
├── bot.py              # Selenium bot for Facebook interaction
├── requirements.txt    # Python dependencies
├── listings.csv        # CSV file containing vehicle listings
├── profile_locations.json  # JSON file for profile locations
├── templates/
│   └── index.html      # HTML template for the web interface
├── static/
│   └── css/
│       └── styles.css  # Custom CSS styles (if any)
└── README.md           # This file
```

## Development

To contribute to the project or customize it for your needs:

1. Fork the repository and create your feature branch:
   ```
   git checkout -b feature/AmazingFeature
   ```

2. Make your changes and commit them:
   ```
   git commit -m 'Add some AmazingFeature'
   ```

3. Push to the branch:
   ```
   git push origin feature/AmazingFeature
   ```

4. Open a pull request

### Adding New Features

- To add new fields to listings, update both `listings.csv` and the `newListing` object in `index.html`
- For new bot functionality, modify `bot.py` and ensure it's properly integrated with `app.py`

### Testing

- Always test your changes thoroughly before committing
- Ensure the bot works correctly with different Chrome profiles and listing combinations

## Troubleshooting

- **CSV Parsing Errors**: If you encounter CSV parsing errors, check your `listings.csv` file for inconsistencies in the number of columns
- **ChromeDriver Issues**: Ensure your ChromeDriver version matches your Chrome browser version
- **Selenium Errors**: Check that the XPaths in `bot.py` are up-to-date with Facebook's current layout

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` file for more information.

---

For any additional questions or support, please open an issue on the GitHub repository.