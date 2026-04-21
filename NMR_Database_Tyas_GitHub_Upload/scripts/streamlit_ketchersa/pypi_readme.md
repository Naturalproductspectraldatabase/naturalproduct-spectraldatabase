[![Open in Huggingface](https://huggingface.co/datasets/huggingface/badges/raw/refs%2Fpr%2F11/open-in-hf-spaces-md-dark.svg)](https://huggingface.co/spaces/z-uo/DrawMaleculeKetcher)

# Streamlit Ketcher Standalone
A Streamlit library for create and open small molecule based on [Ketcher](https://github.com/epam/ketcher/tree/master/packages/ketcher-standalone).

|White theme|
|-----------|
|![streamlit app screenshot](https://gitlab.com/nicolalandro/streamlit-ketchersa/-/raw/main/imgs/white.png)|

Install from pipy:

```
pip install streamlit_ketchersa
```

Example of usage:

```
import streamlit as st
from streamlit_ketchersa import streamlit_ketchersa

result = streamlit_ketchersa()
st.markdown(result)
```