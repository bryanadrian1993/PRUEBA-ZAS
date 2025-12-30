import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
from datetime import datetime

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwzOVH8c8f9WEoE4OJOTIccz_EgrOpZ8ySURTVRwi0bnQhFnWVdgfX1W8ivTIu5dFfs/exec"

# ... (Funciones cargar_datos y enviar_datos se mantienen igual)

with st.expander("📝 FORMULARIO DE REGISTRO"):
    with st.form("registro_form"):
        col1, col2 = st.columns(2)
        with col1:
            r_nom = st.text_input("Nombres *")
            r_ced = st.text_input("Cédula/ID *")
            r_email = st.text_input("Email *")
            r_pais = st.selectbox("País *", ["Ecuador", "Colombia", "Perú", "Otro"])
        with col2:
            r_ape = st.text_input("Apellidos *")
            r_telf = st.text_input("WhatsApp (Sin código) *")
            r_veh = st.selectbox("Tipo de Vehículo *", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
            r_idioma = st.selectbox("Idioma", ["Español", "English"])

        r_dir = st.text_input("Dirección *")
        r_pla = st.text_input("Placa *")
        r_pass1 = st.text_input("Contraseña *", type="password")
        
        if st.form_submit_button("✅ COMPLETAR REGISTRO"):
            if r_nom and r_email and r_pass1:
                res = enviar_datos({
                    "accion": "registrar_conductor", 
                    "nombre": r_nom, "apellido": r_ape, "cedula": r_ced, 
                    "email": r_email, "direccion": r_dir, "telefono": r_telf, 
                    "placa": r_pla, "clave": r_pass1, "pais": r_pais, 
                    "idioma": r_idioma, "tipo_vehiculo": r_veh
                })
                st.success("¡Registro exitoso! Ya puedes ingresar.")
