"""
Práctica APA-T5: Sonido estéreo y ficheros WAVE
Autor: Albert Blázquez Badenas

Este módulo proporciona funciones para la manipulación de canales de audio en ficheros
WAVE (lectura, escritura, conversión mono-estéreo y codificación de 32 bits usando struct).
"""

import struct

def _leer_cabecera(f):
    """
    Lee y valida la cabecera RIFF/WAVE de un archivo de 44 bytes.
    Retorna un diccionario con los metadatos y el tamaño del cacho de datos.
    """
    cabecera = f.read(44)
    if len(cabecera) < 44:
        raise ValueError("El fichero no tiene una cabecera WAVE válida o está truncado.")
    
    campos = struct.unpack('<4sI4s4sIHHIIHH4sI', cabecera)
    
    if campos[0] != b'RIFF' or campos[2] != b'WAVE' or campos[3] != b'fmt ' or campos[11] != b'data':
        raise ValueError("Formato de archivo no soportado o cabecera WAVE corrupta.")
        
    return {
        'chunk_size': campos[1],
        'subchunk1_size': campos[4],
        'audio_format': campos[5],
        'num_channels': campos[6],
        'sample_rate': campos[7],
        'byte_rate': campos[8],
        'block_align': campos[9],
        'bits_per_sample': campos[10],
        'data_size': campos[12]
    }

def _crear_cabecera(num_channels, sample_rate, bits_per_sample, num_samples):
    """
    Genera una cabecera WAVE estándar de 44 bytes para PCM lineal (AudioFormat = 1).
    """
    subchunk2_size = num_samples * num_channels * (bits_per_sample // 8)
    chunk_size = 36 + subchunk2_size
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    
    return struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', chunk_size, b'WAVE', b'fmt ', 16,
        1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample,
        b'data', subchunk2_size
    )

def estereo2mono(ficEste, ficMono, canal=2):
    """
    Lee el fichero ficEste (estéreo, 16 bits) y escribe ficMono (monofónico, 16 bits).
    canal=0: Canal Izquierdo L
    canal=1: Canal Derecho R
    canal=2: Semisuma (L + R) // 2 (Por defecto)
    canal=3: Semidiferencia (L - R) // 2
    """
    if canal not in (0, 1, 2, 3):
        raise ValueError("Canal no válido. Debe ser 0, 1, 2 o 3.")

    with open(ficEste, 'rb') as f_in, open(ficMono, 'wb') as f_out:
        meta = _leer_cabecera(f_in)
        if meta['num_channels'] != 2:
            raise ValueError("El archivo de entrada no es estéreo.")
        if meta['bits_per_sample'] != 16:
            raise ValueError("Solo se soportan archivos WAVE de 16 bits por muestra.")

        num_muestras = meta['data_size'] // 4
        datos_raw = f_in.read(meta['data_size'])
        
        muestras = struct.unpack(f'<{num_muestras * 2}h', datos_raw)
        
        left = muestras[0::2]
        right = muestras[1::2]
        
        if canal == 0:
            mono_muestras = left
        elif canal == 1:
            mono_muestras = right
        elif canal == 2:
            mono_muestras = [(l + r) // 2 for l, r in zip(left, right)]
        elif canal == 3:
            mono_muestras = [(l - r) // 2 for l, r in zip(left, right)]
            
        cabecera_out = _crear_cabecera(1, meta['sample_rate'], 16, num_muestras)
        f_out.write(cabecera_out)
        f_out.write(struct.pack(f'<{num_muestras}h', *mono_muestras))

def mono2estereo(ficIzq, ficDer, ficEste):
    """
    Lee dos ficheros monofónicos (ficIzq y ficDer) de 16 bits y genera
    un archivo estéreo (ficEste) entrelazando sus canales.
    """
    with open(ficIzq, 'rb') as f_izq, open(ficDer, 'rb') as f_der, open(ficEste, 'wb') as f_out:
        meta_izq = _leer_cabecera(f_izq)
        meta_der = _leer_cabecera(f_der)
        
        if meta_izq['num_channels'] != 1 or meta_der['num_channels'] != 1:
            raise ValueError("Los archivos de entrada deben ser monofónicos.")
        if meta_izq['sample_rate'] != meta_der['sample_rate']:
            raise ValueError("Los archivos deben tener la misma frecuencia de muestreo.")
        if meta_izq['bits_per_sample'] != 16 or meta_der['bits_per_sample'] != 16:
            raise ValueError("Solo se soportan archivos de 16 bits.")
            
        num_muestras = min(meta_izq['data_size'], meta_der['data_size']) // 2
        
        left_raw = f_izq.read(num_muestras * 2)
        right_raw = f_der.read(num_muestras * 2)
        
        left = struct.unpack(f'<{num_muestras}h', left_raw)
        right = struct.unpack(f'<{num_muestras}h', right_raw)
        
        estereo_muestras = [val for par in zip(left, right) for val in par]
        
        cabecera_out = _crear_cabecera(2, meta_izq['sample_rate'], 16, num_muestras)
        f_out.write(cabecera_out)
        f_out.write(struct.pack(f'<{num_muestras * 2}h', *estereo_muestras))

def codEstereo(ficEste, ficCod):
    """
    Lee un archivo estéreo de 16 bits y genera un archivo 'monofónico' de 32 bits.
    Los 16 bits más significativos guardan la semisuma (L+R)//2.
    Los 16 bits menos significativos guardan la semidiferencia (L-R)//2.
    """
    with open(ficEste, 'rb') as f_in, open(ficCod, 'wb') as f_out:
        meta = _leer_cabecera(f_in)
        if meta['num_channels'] != 2:
            raise ValueError("El archivo de entrada debe ser estéreo.")
        if meta['bits_per_sample'] != 16:
            raise ValueError("El archivo estéreo debe ser de 16 bits.")
            
        num_muestras = meta['data_size'] // 4
        datos_raw = f_in.read(meta['data_size'])
        muestras = struct.unpack(f'<{num_muestras * 2}h', datos_raw)
        
        left = muestras[0::2]
        right = muestras[1::2]
        
        codificadas = [
            (((l + r) // 2) << 16) | (((l - r) // 2) & 0xFFFF)
            for l, r in zip(left, right)
        ]
        
        cabecera_out = _crear_cabecera(1, meta['sample_rate'], 32, num_muestras)
        f_out.write(cabecera_out)
        f_out.write(struct.pack(f'<{num_muestras}i', *codificadas))

def decEstereo(ficCod, ficEste):
    """
    Lee un archivo de 32 bits codificado (ficCod) y reconstruye el archivo estéreo
    original de 16 bits (ficEste).
    """
    with open(ficCod, 'rb') as f_in, open(ficEste, 'wb') as f_out:
        meta = _leer_cabecera(f_in)
        if meta['num_channels'] != 1 or meta['bits_per_sample'] != 32:
            raise ValueError("El archivo codificado debe ser monofónico de 32 bits.")
            
        num_muestras = meta['data_size'] // 4
        datos_raw = f_in.read(meta['data_size'])
        muestras_32 = struct.unpack(f'<{num_muestras}i', datos_raw)
        
        decodificadas = []
        for m in muestras_32:
            semisuma = m >> 16
            semidiferencia = m & 0xFFFF
            if semidiferencia & 0x8000:
                semidiferencia -= 0x10000
                
            l = semisuma + semidiferencia
            r = semisuma - semidiferencia
            
            l = max(-32768, min(32767, l))
            r = max(-32768, min(32767, r))
            
            decodificadas.extend([l, r])
            
        cabecera_out = _crear_cabecera(2, meta['sample_rate'], 16, num_muestras)
        f_out.write(cabecera_out)
        f_out.write(struct.pack(f'<{num_muestras * 2}h', *decodificadas))