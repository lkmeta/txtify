# YouSub

YouSub is a web application that allows you to easily convert audio and video files to text using AI. You can provide a YouTube URL or upload your own files and use AI models like OpenAI Whisper and Facebook SeamlessM4T for fast and accurate transcriptions.

## Table of Contents

- [About](#about)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Run FREE Online Limited Version](#run-free-online-limited-version)
  - [Self Host](#self-host)
- [Contributing](#contributing)
- [License](#license)

## About

YouSub is designed to simplify the process of converting audio and video content into text. Whether you're looking to transcribe a YouTube video or your own audio/video files, YouSub offers an easy-to-use interface and powerful AI models to ensure accuracy and speed. The application supports multiple output formats including .txt, .pdf, .srt, .vtt, and .sbv.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.x installed on your machine
- Conda installed on your machine
- An API key for DeepL if you want to enable translation

## Installation

To install YouSub, follow these steps:

1. Clone the repository:
   ```sh
   git clone https://github.com/yourrepo/yousub.git
   cd yousub
    ```

Create a conda environment and activate it:

```sh
Copy code
conda create --name yousub python=3.9
conda activate yousub
```

Install the dependencies:

```sh
Copy code
pip install -r requirements.txt
```

## Usage

### Run FREE Online Limited Version

You can use the limited online version of YouSub to get started quickly. Visit [YouSub Online](https://your-online-version-link) and follow the instructions to upload your media or enter a YouTube URL for transcription.

### Self Host

To self-host YouSub with full features, follow these steps:

1. Ensure you have completed the installation steps above.

2. Start the server:
```sh
python app.py
```

3. Open your web browser and navigate to http://localhost:5000 and enjoy.



## Contributing


## License