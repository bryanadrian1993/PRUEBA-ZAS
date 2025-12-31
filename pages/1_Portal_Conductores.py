import streamlit as st
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

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05        
DEUDA_MAXIMA = 10.00        
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO" 

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbxvsj1h8xSsbyIlo7enfZWO2Oe1IVJer3KHpUO_o08gkRGJKmFnH0wNRvQRa38WWKgv/exec"
import requests 

def enviar_datos(params):
    try:
        requests.post(URL_SCRIPT, params=params)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Otro"]
IDIOMAS = ["Español", "English"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]
# --- 🛰️ CAPTURA AUTOMÁTICA DE GPS ---
loc = get_geolocation()
if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']
else:
    lat_actual, lon_actual = None, None
# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    # --- IDs EXTRAÍDOS DE TUS IMÁGENES ---
    GID_CHOFERES = "773119638"
    GID_VIAJES   = "0"
    
    try:
        # Seleccionamos el ID correcto según la hoja que pida el código
        gid_actual = GID_CHOFERES if hoja == "CHOFERES" else GID_VIAJES
        
        # Usamos el enlace de exportación directa (Mucho más estable)
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid_actual}"
        
        # Leemos el archivo CSV
        df = pd.read_csv(url)
        
        # LIMPIEZA VITAL: Quitamos espacios invisibles en los títulos
        df.columns = df.columns.str.strip()
        
        return df
    except Exception as e:
        return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_final = f"{URL_SCRIPT}?{params}"
        with urllib.request.urlopen(url_final) as response:
            return response.read().decode('utf-8')
    except Exception as e: return f"Error: {e}"

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # --- PANEL DEL CONDUCTOR LOGUEADO ---
    df_fresh = cargar_datos("CHOFERES")
    user_nom = str(st.session_state.datos_usuario['Nombre']).strip()
    user_ape = str(st.session_state.datos_usuario['Apellido']).strip()
    
    # Creamos el nombre completo EXACTO para sincronizar con la hoja UBICACIONES
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    # BUSCAMOS LA FILA DEL USUARIO EN EL EXCEL
    fila_actual = df_fresh[
        (df_fresh['Nombre'].astype(str).str.upper().str.strip() == user_nom.upper()) & 
        (df_fresh['Apellido'].astype(str).str.upper().str.strip() == user_ape.upper())
    ]
    
    # --- LÓGICA DE ACTUALIZACIÓN DE UBICACIÓN ---
    st.subheader(f"Bienvenido, {nombre_completo_unificado}")

    # --- 📸 SECCIÓN DE FOTO DE PERFIL ---
    # Buscamos la foto: primero en la sesión (por si acaba de cambiar) y luego en el Excel
    foto_actual = st.session_state.datos_usuario.get('Foto_Perfil', 'SIN_FOTO')
    if foto_actual == "SIN_FOTO" and not fila_actual.empty:
        foto_actual = fila_actual.iloc[0]['Foto_Perfil']

    col_img, col_btn = st.columns([1, 2])

    with col_img:
        if foto_actual and str(foto_actual) != "nan" and len(str(foto_actual)) > 100:
            try:
                img_bytes = base64.b64decode(foto_actual)
                st.image(io.BytesIO(img_bytes), width=150)
            except:
                st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=120)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=120)

    with col_btn:
        st.write("📷 **¿Deseas cambiar tu foto?**")
        archivo_nuevo = st.file_uploader("Sube una imagen (150x150)", type=["jpg", "png", "jpeg"], key="panel_ch_foto")
        
        if archivo_nuevo:
            if st.button("💾 GUARDAR NUEVA FOTO"):
                with st.spinner("Optimizando..."):
                    img = Image.open(archivo_nuevo).convert("RGB")
                    img = img.resize((150, 150)) 
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG", quality=60) 
                    foto_b64 = base64.b64encode(buffered.getvalue()).decode()
                    
                    res = enviar_datos({
                        "accion": "actualizar_foto_perfil",
                        "email": fila_actual.iloc[0]['Email'],
                        "foto": foto_b64
                    })
                    
                    if res:
                        st.success("✅ ¡Foto guardada!")
                        # Actualizamos la foto en la memoria de la App de inmediato
                        st.session_state.datos_usuario['Foto_Perfil'] = foto_b64
                        time.sleep(1) 
                        st.rerun()
    st.write("---") # Separador visual antes del GPS
    # Añadimos 'value=True' para que intente conectar apenas entre
    if st.checkbox("🛰️ ACTIVAR RASTREO GPS", value=True):
        # Usamos las variables lat_actual y lon_actual que definiste en la línea 29
        if lat_actual and lon_actual:
            res = enviar_datos({
                "accion": "actualizar_ubicacion",
                "conductor": nombre_completo_unificado,
                "latitud": lat_actual,
                "longitud": lon_actual
            })
            if res:
                st.success(f"📍 Ubicación activa: {lat_actual}, {lon_actual}")
        else:
            # Esto se quita cuando das clic en 'Hecho' en el navegador
            st.warning("🛰️ Esperando señal de GPS... Por favor, permite el acceso en tu navegador.")
    
    # --- MOSTRAR INFORMACIÓN DEL SOCIO ---
    if not fila_actual.empty:
        # [cite_start]Columna R (Índice 17) es DEUDA [cite: 1]
        deuda_actual = float(fila_actual.iloc[0, 17])
        # [cite_start]Columna I (Índice 8) es Estado [cite: 1]
        estado_actual = str(fila_actual.iloc[0, 8]) 
        
        st.info(f"Estado Actual: **{estado_actual}**")
        st.metric("Tu Deuda Actual:", f"${deuda_actual:.2f}")
        st.success(f"✅ Socio: **{nombre_completo_unificado}**")
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
        col_m2.metric("🚦 Estado Actual", estado_actual)

        # ==========================================
        # 🚀 BLOQUE INTELIGENTE: GESTIÓN DE VIAJE (PAQUETE 2)
        # ==========================================
        st.subheader("Gestión de Viaje")
        
        # 1. Consultamos la hoja VIAJES
        df_viajes = cargar_datos("VIAJES")
        viaje_activo = pd.DataFrame() 

        # 2. Filtramos: ¿Existe un viaje "EN CURSO" para este conductor?
        if not df_viajes.empty and 'Conductor Asignado' in df_viajes.columns:
            viaje_activo = df_viajes[
                (df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado) & 
                (df_viajes['Estado'].astype(str).str.contains("EN CURSO"))
            ]

        # 3. DECISIÓN DEL SISTEMA
        if not viaje_activo.empty:
            # CASO A: HAY PASAJERO -> Mostramos SOLO el botón de Finalizar
            datos_v = viaje_activo.iloc[-1]
            
            st.warning("🚖 TIENES UN PASAJERO A BORDO")
            st.write(f"👤 **Cliente:** {datos_v['Nombre del cliente']}")
            st.write(f"📞 **Tel:** {datos_v['Telefono']}")
            st.write(f"📍 **Destino:** {datos_v['Referencia']}")
            st.markdown(f"[🗺️ Ver Mapa]({datos_v['Mapa']})")

            # --- CÁLCULO DE DISTANCIA REAL GPS ---
            if st.button("🏁 FINALIZAR VIAJE Y COBRAR", type="primary", use_container_width=True):
                with st.spinner("Calculando distancia y cerrando viaje..."):
                    
                    # 1. Valor por defecto de seguridad
                    kms_finales = 5.0 
                    
                    # 2. Intentamos calcular la distancia real entre Cliente y Conductor
                    if lat_actual and lon_actual:
                        try:
                            # Extraemos las coordenadas del cliente desde el link de Google Maps
                            # Tu link es: https://www.google.com/maps/search/?api=1&query=LAT,LON
                            link_mapa = str(datos_v['Mapa'])
                            lat_cliente = float(link_mapa.split('query=')[1].split(',')[0])
                            lon_cliente = float(link_mapa.split('query=')[1].split(',')[1])
                            
                            # Fórmula Matemática Haversine para distancia en la Tierra
                            from math import radians, cos, sin, asin, sqrt
                            def haversine(lat1, lon1, lat2, lon2):
                                R = 6371 # Radio de la Tierra en km
                                dLat = radians(lat2 - lat1)
                                dLon = radians(lon2 - lon1)
                                a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
                                return 2 * R * asin(sqrt(a))
                            
                            kms_finales = haversine(lat_cliente, lon_cliente, lat_actual, lon_actual)
                            
                            # Si es un viaje muy corto, cobramos un mínimo de 1km para ser justos
                            if kms_finales < 0.5: kms_finales = 1.0
                        except:
                            kms_finales = 5.0 # Si el link de mapa falla, vuelve al defecto

                    # 3. ENVIAMOS LOS KM REALES AL SCRIPT
                    res = enviar_datos({
                        "accion": "terminar_viaje", 
                        "conductor": nombre_completo_unificado,
                        "km": round(kms_finales, 2)  # <--- DATO REAL PARA TU PANEL ADMIN
                    })
                    
                    if res:
                        st.success(f"✅ Viaje finalizado: {kms_finales:.2f} km recorridos.")
                        time.sleep(2)
                        st.rerun()
        
        st.divider()
    with st.expander("📜 Ver Mi Historial de Viajes"):
        # Seguridad: Si el bloque anterior no cargó los datos, los cargamos aquí
        if 'df_viajes' not in locals():
            df_viajes = cargar_datos("VIAJES")
            
        if not df_viajes.empty and 'Conductor Asignado' in df_viajes.columns:
            # Filtramos los viajes de este conductor específico
            mis_viajes = df_viajes[df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado]
            
            if not mis_viajes.empty:
                cols_mostrar = ['Fecha', 'Nombre del cliente', 'Referencia', 'Estado']
                cols_finales = [c for c in cols_mostrar if c in mis_viajes.columns]
                st.dataframe(mis_viajes[cols_finales].sort_values(by='Fecha', ascending=False), use_container_width=True)
            else:
                st.info("Aún no tienes historial de viajes.")
        else:
            st.write("Cargando datos...")    
    
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()
    st.stop()
else:
    # --- PANTALLA INICIAL: LOGIN Y REGISTRO ---
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])


    
    with tab_log:
        st.subheader("Acceso Socios")
        l_nom = st.text_input("Nombre registrado")
        l_ape = st.text_input("Apellido registrado")
        l_pass = st.text_input("Contraseña", type="password")
        
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            # Validación por Nombre, Apellido y Clave
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & 
                       (df['Apellido'].astype(str).str.upper() == l_ape.upper()) & 
                       (df['Clave'].astype(str) == l_pass)]
            
            if not match.empty:
                st.session_state.usuario_activo = True
                st.session_state.datos_usuario = match.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("❌ Datos incorrectos o usuario no encontrado.")
    st.markdown("---") 
with st.expander("¿Olvidaste tu contraseña?"):
    st.info("Ingresa tu correo registrado para recibir tu clave:")
    email_recup = st.text_input("Tu Email", key="email_recup")
    
    if st.button("📧 Recuperar Clave"):
        if "@" in email_recup:
            with st.spinner("Conectando con el sistema..."):
                try:
                    # Petición al Script de Google
                    resp = requests.post(URL_SCRIPT, params={
                        "accion": "recuperar_clave",
                        "email": email_recup
                    })
                    
                    if "CORREO_ENVIADO" in resp.text:
                        st.success("✅ ¡Enviado! Revisa tu correo (Bandeja de entrada o Spam).")
                    elif "EMAIL_NO_ENCONTRADO" in resp.text:
                        st.error("❌ Ese correo no está registrado como socio.")
                    else:
                        st.error("Error de conexión.")
                except:
                    st.error("Error al conectar con el servidor.")
        else:
            st.warning("Escribe un correo válido.")
    with tab_reg:
        with st.form("registro_form"):
            st.subheader("Registro de Nuevos Socios")
            col1, col2 = st.columns(2)
            with col1:
                r_nom = st.text_input("Nombres *")
                r_ced = st.text_input("Cédula/ID *")
                r_email = st.text_input("Email *")
                r_pais = st.selectbox("País *", PAISES)
            with col2:
                r_ape = st.text_input("Apellidos *")
                r_telf = st.text_input("WhatsApp (Sin código) *")
                r_veh = st.selectbox("Tipo de Vehículo *", VEHICULOS)
                r_idioma = st.selectbox("Idioma", IDIOMAS)
    
            r_dir = st.text_input("Dirección *")
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            
            # --- 📸 1. NUEVO: CAMPO PARA SUBIR FOTO ---
            st.write("---")
            st.write("📷 **Foto de Perfil** (Opcional)")
            archivo_foto_reg = st.file_uploader("Sube tu foto", type=["jpg", "png", "jpeg"])
            # ------------------------------------------
            
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_email and r_pass1:
                    
                    # --- ⚙️ 2. NUEVO: PROCESAR FOTO A BASE64 ---
                    foto_para_guardar = "SIN_FOTO" # Valor por defecto
    
                    if archivo_foto_reg is not None:
                        try:
                            img = Image.open(archivo_foto_reg)
                            img = img.resize((150, 150)) # Reducir tamaño
                            buffered = io.BytesIO()
                            img.save(buffered, format="JPEG", quality=70)
                            foto_para_guardar = base64.b64encode(buffered.getvalue()).decode()
                        except Exception as e:
                            st.error(f"Error procesando la imagen: {e}")
                    # ---------------------------------------------
    
                    # --- 📤 3. AGREGAMOS LA FOTO AL ENVÍO ---
                    res = enviar_datos({
                        "accion": "registrar_conductor", 
                        "nombre": r_nom, 
                        "apellido": r_ape, 
                        "cedula": r_ced, 
                        "email": r_email, 
                        "direccion": r_dir, 
                        "telefono": r_telf, 
                        "placa": r_pla, 
                        "clave": r_pass1, 
                        "foto": foto_para_guardar,  # <--- AQUÍ VA LA FOTO NUEVA
                        "pais": r_pais, 
                        "idioma": r_idioma, 
                        "Tipo_Vehiculo": r_veh
                    })
                    
                    # Mensaje de éxito o error según responda tu función
                    if res: 
                        st.success("¡Registro exitoso! Ya puedes ingresar desde la pestaña superior.")
                else:
                    st.warning("Por favor, completa los campos obligatorios (*)")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)
# 👇 PEGA ESTO AL FINAL DEL ARCHIVO (Línea 260 en adelante) 👇

import time

# El Radar: Solo se activa si hay un usuario logueado y está LIBRE
if st.session_state.get('usuario_activo', False):
    # Buscamos el estado dentro de los datos guardados en sesión
    datos = st.session_state.get('datos_usuario', {})
    estado_chofer = datos.get('estado', 'OCUPADO') # Por seguridad asumimos ocupado si falla
    
    # Si está LIBRE, activamos el conteo regresivo
    if "LIBRE" in str(estado_chofer):
        time.sleep(15)  # Espera 15 segundos
        st.rerun()      # Recarga la página para buscar viajes nuevos
