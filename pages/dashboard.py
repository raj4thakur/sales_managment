import streamlit as st
import streamlit.components.v1 as components

def create_dashboard(db=None, analytics=None):
    # DO NOT call st.set_page_config here
    st.markdown("<h1 class='main-header'>📊 Power BI Dashboard</h1>", unsafe_allow_html=True)
    components.iframe(
        src="https://app.powerbi.com/view?r=eyJrIjoiM2VmZDQxNTUtMGEyYS00NDNiLWEyMDMtZWY5MGFkYTlmYjU2IiwidCI6ImFmYTM1MTRhLTFlNDItNDBjOS04ZjExLWIzODNlNmRhYTM3NiIsImMiOjN9",
        width=1200,
        height=800,
        scrolling=True
    )
