import os
import struct
import sys
import time
from bit_stream import BitWriter
from shannon import generate_shannon_o2_codes, get_pairs_and_padding

def compress(input_path: str, output_path: str):
    """Comprime un archivo utilizando el algoritmo Shannon O(2) y genera un archivo .tdi."""
    if not os.path.exists(input_path):
        print(f"Error: El archivo de entrada '{input_path}' no existe.")
        sys.exit(1)

    start_time = time.time() # mover abajo de la lectura del archivo?

    # 1. Leer archivo original en modo binario
    with open(input_path, "rb") as f:
        original_data = f.read()

    original_size = len(original_data)

    if original_size == 0:
        print("Error: El archivo de entrada esta vacio.")
        sys.exit(1)
    
    # 2. Convertir a pares de bytes y calcular códigos Shannon O(2)
    pairs, has_padding = get_pairs_and_padding(original_data)
    codes, freq_map = generate_shannon_o2_codes(pairs)

    # 3. Escribir el archivo comprimido .tdi
    with open(output_path, "wb") as out_file:
        # A. Escribir Cabecera
        # - Magic Bytes: "TDI1" (4 bytes)
        out_file.write(b"TDI1")

        # - Tamaño original (8 bytes) y bandera de padding (1 byte)
        out_file.write(
            struct.pack(">QB", original_size, 1 if has_padding else 0)
        )

        # - Cantidad de entradas en la tabla de frecuencias (2 bytes)
        num_entries = len(freq_map)
        out_file.write(struct.pack(">H", num_entries))

        # - Escribir el diccionario (Par de bytes: 2B + Frecuencia: 4B)
        for (b1, b2), count in freq_map.items():
            out_file.write(bytes([b1, b2]))
            out_file.write(struct.pack(">I", count))

        header_size = out_file.tell()

        # B. Escribir Cuerpo Comprimido
        writer = BitWriter(out_file)
        for pair in pairs:
            code = codes[pair]
            writer.write_bits(code)

        # Vaciar bits restantes acumulados en el buffer
        writer.flush()

    elapsed_time_ms = (time.time() - start_time) * 1000
    compressed_size = os.path.getsize(output_path)

    # 4. Calcular Métricas de Rendimiento
    ratio = original_size / compressed_size if compressed_size > 0 else 0
    saving_pct = (1 - (compressed_size / original_size)) * 100
    overhead_pct = (header_size / compressed_size) * 100

    # 5. Salida Mínima en Pantalla requerida por la Cátedra
    print("=" * 60)
    print("             COMPRESIÓN COMPLETADA (Shannon O(2))           ")
    print("=" * 60)
    print(f"Archivo de entrada  : {input_path}")
    print(f"Archivo de salida   : {output_path}")
    print(f"Tamaño original     : {original_size:,} bytes")
    print(f"Tamaño cabecera     : {header_size:,} bytes")
    print(f"Tamaño comprimido   : {compressed_size:,} bytes")
    print(f"Ratio de compresión : {ratio:.4f}")
    print(f"Ahorro de espacio   : {saving_pct:.2f}%")
    print(f"Overhead cabecera   : {overhead_pct:.2f}%")
    print(f"Tiempo de ejecución : {elapsed_time_ms:.2f} ms")
    print("Parámetros          : Orden de contexto = 2 (Pares de bytes)")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python compressor.py <archivo_entrada> <salida.tdi>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    compress(input_file, output_file)