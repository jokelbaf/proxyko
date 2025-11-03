<div align="center" width="100%">
    <img src="static/img/logo.png" width="128" alt="" />
</div>

<h1 align="center">Proxyko</h1>

<div align="center">

<a href="">![Python](https://img.shields.io/badge/Python-df6747?style=for-the-badge&logo=python&logoColor=white)</a>
<a href="">![FastAPI](https://img.shields.io/badge/FastAPI-df6747.svg?style=for-the-badge&logo=fastapi&logoColor=white)</a>
<a href="">![Chart.js](https://img.shields.io/badge/Chart.js-df6747?style=for-the-badge&logo=chartdotjs&logoColor=white)</a>
<a href="">![Docker](https://img.shields.io/badge/Docker-df6747?style=for-the-badge&logo=docker&logoColor=white)</a>

</div>

<p align="center">
Proxyko is a powerful Proxy Auto-Configuration (PAC) service with a built-in forwarding proxy that allows users to manage per-device proxy settings through a user-friendly web dashboard.
</p>

## Preview
<img src="assets/demo.png" alt="" width="80%"/>

## Features

Proxyko offers a range of features to simplify proxy configuration management:
- **User-friendly Dashboard**: An intuitive web interface for service configuration.
- **Per-Device Proxy Settings**: Assign unique proxy configurations to each device using secure tokens.
- **IP-based Access Control**: Restrict device access based on IP addresses for improved security.
- **Real-time Monitoring**: Track and analyze service usage statistics through the dashboard.
- **2FA Support**: Enhance account security with two-factor authentication.
- **Built-in Proxy Server**: An optional integrated [proxy server](https://github.com/jokelbaf/proxyko-proxy) with advanced rule configuration.

## Installation

The preferred way to run Proxyko is via Docker Compose. Simply clone the repo, edit [`docker-compose.yml`](docker-compose.yml) to set the required environment variables, and run:
```bash
docker-compose up -d
```

The service will then be accessible at `http://localhost:8032` by default.

## Development

Contributions are welcome! To set up a development environment, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/jokelbaf/proxyko.git
   cd proxyko
   ```
2. Create a virtual environment:
   ```bash
   uv sync --dev
   ```
3. Configure environment variables:
   Create a `.env` file in the root directory and set the necessary environment variables as per the `.env.example` file.
4. Run the application:
   ```bash
   uv run src/app.py
   ```

To work with proxy-related features, you'll need to clone and run the [proxy server](https://github.com/jokelbaf/proxyko-proxy) separately.

## Motivation

I love watching anime on Crunchyroll, but some shows have broken subtitles on mobile devices. I initially wrote a simple proxy server using MITMProxy to automatically fix the subtitles, but turning it on and off and configuring proxy settings on my iPhone every time was a pain. I explored different options and discovered PAC files, which allow automatic proxy configuration based on rules. However, managing PAC files manually was cumbersome, so I decided to create Proxyko to streamline the process. I deployed both it and my proxy on a dedicated server, so now I can toggle the proxy on my phone with just a few taps :)

## License

The project is licensed under the [MIT License](LICENSE.md). Enjoy!
