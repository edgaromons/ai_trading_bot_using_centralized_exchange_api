# ai_trading_bot_using_centralized_exchange_api
In this project, we demonstrate how to build an AI trading bot using a Centralized Exchange's API.

We basically:

•	Utilized Python and the Alpaca API to develop and deploy an automated trading bot for stocks and cryptocurrencies.

•	Developed a web scraper using Python and the requests-html library to gather financial data from Yahoo Finance.

•	Implemented technical trading strategies, including Bollinger Bands and RSI, using the ta library in Python.

•	Integrated the Slack API to send real-time trade notifications.

•	Built a cryptocurrency trading bot using machine learning and the LSTM model in TensorFlow Keras.

•	Analyzed market data from Alpaca to train and evaluate the trading model's performance.

•	Used the yfinance library to retrieve historical stock and cryptocurrency data.

•	Managed and tracked portfolio positions and performance using the Alpaca API.

•	Configured and integrated CircleCI for continuous integration and deployment of the trading bot.

Installing Dependencies from requirements.txt

Follow these steps to install the required Python dependencies on your system.

✅ Prerequisites:

•	Ensure Python (>=3.x) and pip (>=21.x) are installed.
•	Check Python and pip versions:
sh
CopyEdit
python --version
pip --version

📌 Installation Instructions

🖥️ Windows:

1.	Open Command Prompt or PowerShell.
2.	Navigate to the project directory:
sh
CopyEdit
cd path\to\your\project
3.	Run:
sh
CopyEdit
pip install -r requirements.txt

🍏 macOS & 🐧 Linux:

1.	Open Terminal.
2.	Navigate to the project directory:
sh
CopyEdit
cd /path/to/your/project
3.	Run:
sh
CopyEdit
pip install -r requirements.txt

🔍 Additional Tips:

•	If using a virtual environment, activate it before running the installation:
sh
CopyEdit

# Windows (CMD)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate
•	If you face permission issues, try:
sh
CopyEdit
pip install --user -r requirements.txt

•	For system-wide installation, use:

sh
CopyEdit
sudo pip install -r requirements.txt

🛠️ Verifying Installation:

Run:
sh
CopyEdit
pip list
to check if all packages are installed.

