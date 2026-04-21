import os
import streamlit.components.v1 as components

_RELEASE = True

if not _RELEASE:
  _component_func = components.declare_component(
    "streamlit_ketchersa",
    url="http://localhost:5173", # vite dev server port
  )
else:
  parent_dir = os.path.dirname(os.path.abspath(__file__))
  build_dir = os.path.join(parent_dir, "frontend/dist")
  _component_func = components.declare_component("streamlit_ketchersa", path=build_dir)

def streamlit_ketchersa(height='50%', key=None):
  component_value = _component_func(heigth=height, key=key, default=0)
  return component_value

if not _RELEASE:
  import streamlit as st
  st.subheader("Component Test")
  result = streamlit_ketchersa()
  st.markdown(result)