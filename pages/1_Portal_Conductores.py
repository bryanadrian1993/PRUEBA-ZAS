import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import urllib.parse
import urllib.request
import base64
import math
import os
import time
import io
from PIL import Image
from datetime import datetime
from streamlit_js_eval import get_geolocation
import requests
import streamlit.components.v1 as components

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")

# --- 🔌 CONEXIÓN SEGURA A GOOGLE SHEETS ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"⚠️ Error de configuración de secretos: {e}")

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05
DEUDA_MAXIMA = 10.00
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO"
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state:
    st.session_state['usuario_activo'] = False
if 'datos_usuario' not in st.session_state:
    st.session_state['datos_usuario'] = {}

# --- FUNCIÓN DE PAGO PAYPAL ---
def mostrar_boton_pago(monto_deuda):
    st.header("🔓 Desbloqueo Automático (PayPal)")
    st.warning(f"Tu deuda es de **${monto_deuda:.2f}**. Debes pagarla completa para desbloquearte.")
    
    cedula_conductor = st.text_input("Ingresa tu número de identificación:", max_chars=15)
    
    if cedula_conductor:
        client_id = "AS96Gq4_mueF7i7xjUzx2nEgYSmiS6t69datLVrPMwxDIxboQC00sZf7TBM6KwkRxUL92ys0I-JXXq_y"
        valor_a_pagar = f"{monto_deuda:.2f}"
        
        _html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                html, body {{ margin: 0; padding: 0; height: 100%; overflow: auto; }}
                #paypal-button-container-final {{ min_height: 600px; width: 100%; }}
            </style>
        </head>
        <body>
            <div id="paypal-button-container-final"></div>
            <script src="https://www.paypal.com/sdk/js?client-id={client_id}&currency=USD&components=buttons"></script>
            <script>
                paypal.Buttons({{
                    style: {{
                        layout: 'vertical',
                        color:  'gold',
                        shape:  'rect',
                        label:  'pay',
                        disableMaxWidth: true 
                    }},
                    createOrder: function(data, actions) {{
                        return actions.order.create({{
                            purchase_units: [{{
                                amount: {{ value: '{valor_a_pagar}' }},
                                custom_id: '{cedula_conductor}'
                            }}]
                        }});
                    }},
                    onApprove: function(data, actions) {{
                        return actions.order.capture().then(function(details) {{
                            alert('¡Pago de ${valor_a_pagar} Exitoso! Tu cuenta se está desbloqueando...');
                        }});
                    }},
                    onError: function (err) {{
                        console.error('Error:', err);
                        alert('No se pudo cargar el formulario de pago.');
                    }}
                }}).render('#paypal-button-container-final');
            </script>
        </body>
        </html>
        """
        st.caption(f"Total a pagar para desbloqueo: ${valor_a_pagar}")
        components.html(_html, height=700, scrolling=True)
    else:
        st.info("👆 Escribe tu identificación para ver el botón de pago.")

# --- 🛠️ FUNCIONES DE ESCRITURA DIRECTA ---

def actualizar_gps_excel(conductor, lat, lon):
    try:
        sh = client.open_by_key(SHEET_ID)
        try:
            wks = sh.worksheet("UBICACIONES")
        except:
            wks = sh.add_worksheet(title="UBICACIONES", rows=1000, cols=5)
            wks.append_row(["Conductor", "Latitud", "Longitud", "Ultima_Actualizacion"])
        
        conductores = wks.col_values(1)
        nombre_limpio = conductor.strip().upper()
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            fila = conductores.index(nombre_limpio) + 1
            wks.update_cell(fila, 2, lat)
            wks.update_cell(fila, 3, lon)
            wks.update_cell(fila, 4, ahora)
        except ValueError:
            wks.append_row([nombre_limpio, lat, lon, ahora])
        return True
    except: return False

def actualizar_estado_por_email(email_usuario, nuevo_estado):
    try:
        sh = client.open_by_key(SHEET_ID)
        wks = sh.worksheet("CHOFERES")
        emails = wks.col_values(5) 
        try:
            fila = emails.index(email_usuario) + 1
            wks.update_cell(fila, 9, nuevo_estado)
            return True
        except ValueError:
            return False
    except Exception as e:
        return False

def cargar_datos(hoja):
    try:
        sh = client.open_by_key(SHEET_ID)
        wks = sh.worksheet(hoja)
        data = wks.get_all_values()
        if not data: return pd.DataFrame()
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return pd.DataFrame()

def enviar_datos_requests(params):
    try:
        requests.post(URL_SCRIPT, params=params)
    except: pass

# --- 🛰️ CAPTURA GPS ---
loc = get_geolocation()
lat_actual, lon_actual = None, None
if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Otro"]
IDIOMAS = ["Español", "English"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.get('usuario_activo', False):
    # --- PANEL CHOFER ---
    df_fresh = cargar_datos("CHOFERES")
    if df_fresh.empty:
        st.error("Error conectando con la base de datos.")
        st.stop()

    datos = st.session_state.datos_usuario
    user_nom = str(datos.get('Nombre', '')).strip()
    user_ape = str(datos.get('Apellido', '')).strip()
    user_email = str(datos.get('Email', '')).strip()
    
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    st.subheader(f"Bienvenido, {nombre_completo_unificado}")

    foto = datos.get('Foto_Perfil', 'SIN_FOTO')
    c1, c2 = st.columns([1, 2])
    with c1:
        if len(str(foto)) > 100:
            try: st.image(io.BytesIO(base64.b64decode(foto)), width=120)
            except: st.write("👤")
        else: st.write("👤 Sin foto")
    
    with c2:
        st.info(f"📧 {user_email}")

    st.divider()

    gps_activo = st.checkbox("🛰️ RASTREO GPS ACTIVO", value=True)
    
    if gps_activo:
        if lat_actual and lon_actual:
            actualizar_gps_excel(nombre_completo_unificado, lat_actual, lon_actual)
            st.success(f"✅ GPS Transmitiendo: {lat_actual:.4f}, {lon_actual:.4f}")
        else:
            st.warning("⚠️ Buscando señal GPS...")
    
    # --- SECCIÓN ESTADO ---
    st.subheader("Tu Estado")
    
    fila_usuario = df_fresh[df_fresh['Email'] == user_email]
    if not fila_usuario.empty:
        estado_actual_db = fila_usuario.iloc[0]['Estado']
        deuda_actual = float(str(fila_usuario.iloc[0]['DEUDA']).replace(',', '').replace('$', '') or 0)
    else:
        estado_actual_db = "DESCONOCIDO"
        deuda_actual = 0.0

    c_lib, c_ocu = st.columns(2)
    
    with c_lib:
        if st.button("🟢 PONERME LIBRE", use_container_width=True):
            if deuda_actual >= DEUDA_MAXIMA:
                st.error(f"🚫 DEUDA PENDIENTE: ${deuda_actual}")
            else:
                with st.spinner("Actualizando..."):
                    if actualizar_estado_por_email(user_email, "LIBRE"):
                        if lat_actual: actualizar_gps_excel(nombre_completo_unificado, lat_actual, lon_actual)
                        st.success("✅ ¡AHORA ESTÁS LIBRE!")
                        time.sleep(1)
                        st.rerun()
    
    with c_ocu:
        if st.button("🔴 PONERME OCUPADO", use_container_width=True):
            actualizar_estado_por_email(user_email, "OCUPADO")
            st.warning("🔴 Estás OCUPADO")
            time.sleep(1)
            st.rerun()

    st.metric("Estado en Base de Datos", estado_actual_db)
    
    if deuda_actual > 0:
        st.divider()
        st.error(f"💰 Deuda Actual: ${deuda_actual:.2f}")
        if deuda_actual >= DEUDA_MAXIMA:
            st.write("Debes pagar para desbloquearte.")
            mostrar_boton_pago(deuda_actual)
    
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()

else:
    # --- LOGIN / REGISTRO ---
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    
    with tab_log:
        st.subheader("Ingreso de Socios")
        l_email = st.text_input("Email registrado:")
        l_pass = st.text_input("Contraseña:", type="password")
        
        if st.button("ENTRAR", type="primary"):
            df = cargar_datos("CHOFERES")
            if not df.empty:
                user = df[
                    (df['Email'].str.strip() == l_email.strip()) & 
                    (df['Clave'].str.strip() == l_pass.strip())
                ]
                if not user.empty:
                    st.session_state.usuario_activo = True
                    st.session_state.datos_usuario = user.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
            else:
                st.error("Error conectando a base de datos")

    with tab_reg:
        with st.form("registro_form"):
            st.subheader("Registro Nuevo Conductor")
            c1, c2 = st.columns(2)
            with c1:
                r_nom = st.text_input("Nombres *")
                r_ced = st.text_input("Cédula/ID *")
                r_email = st.text_input("Email *")
                r_pais = st.selectbox("País *", PAISES)
            with c2:
                r_ape = st.text_input("Apellidos *")
                r_telf = st.text_input("WhatsApp *")
                # AQUÍ SE SELECCIONA EL VEHÍCULO
                r_veh = st.selectbox("Tipo de Vehículo *", VEHICULOS)
                r_idioma = st.selectbox("Idioma", IDIOMAS)
            
            r_dir = st.text_input("Dirección *")
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            
            archivo_foto = st.file_uploader("Foto de Perfil", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("✅ REGISTRARME"):
                if r_nom and r_email and r_pass1 and r_veh:
                    foto_b64 = "SIN_FOTO"
                    if archivo_foto:
                        try:
                            img = Image.open(archivo_foto).convert('RGB').resize((150,150))
                            buf = io.BytesIO()
                            img.save(buf, format="JPEG", quality=60)
                            foto_b64 = base64.b64encode(buf.getvalue()).decode()
                        except: pass

                    try:
                        with st.spinner("Guardando en Excel..."):
                            sh = client.open_by_key(SHEET_ID)
                            wks = sh.worksheet("CHOFERES")
                            
                            # --- ORDEN EXACTO DE COLUMNAS A-R ---
                            nueva_fila = [
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # A
                                r_nom, # B
                                r_ape, # C
                                r_ced, # D
                                r_email, # E
                                r_dir, # F
                                r_telf, # G
                                r_pla, # H
                                "LIBRE", # I (Estado Inicial)
                                "", # J
                                r_pass1, # K
                                foto_b64, # L
                                "SI", # M
                                r_pais, # N
                                r_idioma, # O
                                r_veh, # P -> AQUÍ SE GUARDA EL TIPO DE VEHÍCULO
                                0, # Q
                                0.00 # R
                            ]
                            wks.append_row(nueva_fila)
                            st.success("¡Registro Exitoso! Ya puedes ingresar.")
                            st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Llena los campos obligatorios.")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)
