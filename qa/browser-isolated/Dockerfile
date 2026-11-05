FROM mcr.microsoft.com/playwright/python:v1.64.1-noble
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir \
    playwright==1.64.1 streamlit==1.66.1 pandas==2.2.3 rdkit==2026.9.1 \
    plotly==7.1.0 Pillow==12.3.0 openpyxl==3.1.5
RUN /venv/bin/python -m pip check
COPY app /baseline
COPY shipped-config.toml /baseline-config.toml
COPY fixture.py browser_qa.py /qa/
RUN /venv/bin/python -m py_compile /qa/fixture.py /qa/browser_qa.py
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["/venv/bin/python", "/qa/browser_qa.py"]
