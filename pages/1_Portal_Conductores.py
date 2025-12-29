import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
import base64
import math
import os
import re
from datetime import datetime
from streamlit_js_eval import get_geolocation

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05        
DEUDA_MAXIMA = 10.00        
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO" 
NUMERO_DEUNA = "09XXXXXXXX" 

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
# ✅ URL VINCULADA CORRECTAMENTE
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwmdasUK1xYWaJjk-ytEAjepFazngTZ91qxhsuN0VZ0OgQmmjyZnD6nOnCNuwIL3HjD/exec"

# ... (Se mantienen tus funciones cargar_datos, enviar_datos y calcular_distancia)

# --- PANEL DE REGISTRO (Dentro de la pestaña '📝 REGISTRARME') ---
# He verificado que esta sección envíe 'tipo_vehiculo' tal cual lo espera el Script de arriba
res = enviar_datos({
    "accion": "registrar_conductor", 
    "nombre": r_nom, 
    "apellido": r_ape, 
    "email": r_email, 
    "cedula": r_ced, 
    "direccion": r_dir,
    "pais": r_pais,
    "telefono": r_telf, 
    "tipo_vehiculo": r_veh, # ✅ SINCRONIZADO
    "placa": r_pla, 
    "clave": r_pass1
})
