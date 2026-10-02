import csv
import json
import math
import os
import subprocess
import sys
import time

# --- CONFIGURACIÓN DE PRUEBAS ---
# Asegurate de colocar los archivos de prueba en la carpeta 'tests/'
TEST_FILES = [
    "tests/prueba_1_pequena.txt",  # Prueba 1: Muy pequeño (< 1 KiB)
    "tests/prueba_2_texto_natural.txt",  # Prueba 2: Texto natural (>= 1 MiB)
    "tests/prueba_3_alta_repeticion.txt",  # Prueba 3: Alta repetición (>= 1 MiB)
    "tests/prueba_4_baja_repeticion.txt",  # Prueba 4: Baja repetición (>= 1 MiB)
]

RESULTS_DIR = "results"
TEMP_DIR = "temp_benchmark"


def ensure_directories():
    """Crea carpetas necesarias si no existen."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)


def measure_shannon_o2(input_path):
    """Mide compresión con el compresor propio Python."""
    out_path = os.path.join(
        TEMP_DIR, os.path.basename(input_path) + ".shannon.tdi"
    )

    start = time.perf_counter()
    res = subprocess.run(
        [sys.executable, "compressor.py", input_path, out_path],
        capture_output=True,
        text=True,
    )
    end = time.perf_counter()

    if res.returncode != 0:
        print(f"Error ejecutando Shannon O(2): {res.stderr}")
        return None, None

    elapsed_ms = (end - start) * 1000
    compressed_size = os.path.getsize(out_path)
    return compressed_size, elapsed_ms


def measure_7zip(input_path):
    """Mide compresión con 7-Zip (LZMA2 Preset Normal)."""
    out_path = os.path.join(TEMP_DIR, os.path.basename(input_path) + ".7z")
    if os.path.exists(out_path):
        os.remove(out_path)

    cmd = ["7z", "a", "-t7z", "-m0=LZMA2", "-mx=5", out_path, input_path]

    start = time.perf_counter()
    res = subprocess.run(cmd, capture_output=True, text=True)
    end = time.perf_counter()

    if res.returncode != 0:
        # Intento alternativo para entornos donde el binario se llama '7za'
        cmd[0] = "7za"
        start = time.perf_counter()
        res = subprocess.run(cmd, capture_output=True, text=True)
        end = time.perf_counter()
        if res.returncode != 0:
            print(
                f"Error ejecutando 7-Zip. Verifique instalacion de '7z': {res.stderr}"
            )
            return None, None

    elapsed_ms = (end - start) * 1000
    compressed_size = os.path.getsize(out_path)
    return compressed_size, elapsed_ms


def measure_gzip6(input_path):
    """Mide compresión con gzip -6 (Baseline de la Cátedra)."""
    out_path = os.path.join(TEMP_DIR, os.path.basename(input_path) + ".gz")

    start = time.perf_counter()
    with open(input_path, "rb") as f_in, open(out_path, "wb") as f_out:
        res = subprocess.run(
            ["gzip", "-n", "-6", "-c"],
            stdin=f_in,
            stdout=f_out,
            capture_output=False,
        )
    end = time.perf_counter()

    if res.returncode != 0:
        print("Error ejecutando gzip.")
        return None, None

    elapsed_ms = (end - start) * 1000
    compressed_size = os.path.getsize(out_path)
    return compressed_size, elapsed_ms


def calculate_weissman(
    r_sol, r_ref, t_sol_ms, t_ref_ms, alpha=1.0, epsilon=1e-6
):
    """
    Calcula el Weissman Score: W = alpha * (R / Rref) * [log(Tref) / log(T)]
    Los tiempos deben expresarse obligatoriamente en milisegundos.
    """
    if (
        r_ref <= 0
        or r_sol <= 0
        or t_sol_ms <= 0
        or t_ref_ms <= 0
        or (t_sol_ms + epsilon) <= 1
        or (t_ref_ms + epsilon) <= 1
    ):
        return 1.0

    log_t_ref = math.log(max(t_ref_ms, 1.0001))
    log_t_sol = math.log(max(t_sol_ms, 1.0001))

    weissman = alpha * (r_sol / r_ref) * (log_t_ref / log_t_sol)
    return weissman


def run_benchmark():
    ensure_directories()
    results = []

    print("=" * 80)
    print("               EJECUTANDO BENCHMARK GLOBAL DE COMPRESIÓN            ")
    print("=" * 80)

    for test_file in TEST_FILES:
        if not os.path.exists(test_file):
            print(
                f"Saltando '{test_file}': archivo no encontrado en disco."
            )
            continue

        orig_size = os.path.getsize(test_file)
        file_name = os.path.basename(test_file)
        print(f"\nProcesando archivo: {file_name} ({orig_size:,} bytes)...")

        # 1. Medir gzip-6 (Baseline)
        gz_size, gz_time = measure_gzip6(test_file)
        if not gz_size:
            continue
        r_gz = orig_size / gz_size

        # 2. Medir Shannon O(2) (Propio)
        sh_size, sh_time = measure_shannon_o2(test_file)

        # 3. Medir 7-Zip LZMA2 (Externo)
        z7_size, z7_time = measure_7zip(test_file)

        # Calcular ratios y Weissman
        if sh_size and sh_time:
            r_sh = orig_size / sh_size
            w_sh = calculate_weissman(r_sh, r_gz, sh_time, gz_time)
            results.append(
                {
                    "Archivo": file_name,
                    "Algoritmo": "Shannon O(2) (Propio)",
                    "Tam_Original": orig_size,
                    "Tam_Comprimido": sh_size,
                    "Ratio": round(r_sh, 4),
                    "Tiempo_ms": round(sh_time, 2),
                    "Ratio_gzip": round(r_gz, 4),
                    "Tiempo_gzip_ms": round(gz_time, 2),
                    "Weissman": round(w_sh, 4),
                }
            )

        if z7_size and z7_time:
            r_z7 = orig_size / z7_size
            w_z7 = calculate_weissman(r_z7, r_gz, z7_time, gz_time)
            results.append(
                {
                    "Archivo": file_name,
                    "Algoritmo": "7-Zip LZMA2 (Externo)",
                    "Tam_Original": orig_size,
                    "Tam_Comprimido": z7_size,
                    "Ratio": round(r_z7, 4),
                    "Tiempo_ms": round(z7_time, 2),
                    "Ratio_gzip": round(r_gz, 4),
                    "Tiempo_gzip_ms": round(gz_time, 2),
                    "Weissman": round(w_z7, 4),
                }
            )

        # Registrar baseline
        results.append(
            {
                "Archivo": file_name,
                "Algoritmo": "gzip -6 (Baseline)",
                "Tam_Original": orig_size,
                "Tam_Comprimido": gz_size,
                "Ratio": round(r_gz, 4),
                "Tiempo_ms": round(gz_time, 2),
                "Ratio_gzip": round(r_gz, 4),
                "Tiempo_gzip_ms": round(gz_time, 2),
                "Weissman": 1.0000,
            }
        )

    # Exportar resultados a CSV
    csv_path = os.path.join(RESULTS_DIR, "benchmark_results.csv")
    if results:
        keys = results[0].keys()
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(results)

        print("\n" + "=" * 80)
        print(f"TABLA RESUMEN DE RESULTADOS (Guardado en '{csv_path}'):")
        print("=" * 80)
        print(
            f"{'Archivo':<22} | {'Algoritmo':<22} | {'Ratio':<7} | {'Tiempo (ms)':<11} | {'Weissman':<8}"
        )
        print("-" * 80)
        for row in results:
            print(
                f"{row['Archivo']:<22} | {row['Algoritmo']:<22} | {row['Ratio']:<7.2f} | {row['Tiempo_ms']:<11.2f} | {row['Weissman']:<8.4f}"
            )
        print("=" * 80)


if __name__ == "__main__":
    run_benchmark()