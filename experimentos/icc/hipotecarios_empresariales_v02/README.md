# ICC empresarial 0.2 — pesos cerrados

Esta carpeta forma parte del proyecto depurado. Usa código o insumos compartidos
con las otras carpetas del proyecto; ejecutar dentro de la carpeta `proyecto`
completa. El punto de entrada es `../../../LEEME_ICC.md`.


PyMEs 935: 60/40. No PyMEs 936: 80/20. Uso descriptivo interno experimental.

Leer cierre_pesos_icc_v02.md. Ejecutar desde esta carpeta:

    python -m pip install -r ../../../requirements_icc.txt
    python cierre_icc.py --apply
    python -m unittest validar_cierre -v

Conserva fuentes congeladas y decisión. No refit, sin red, reserva sin score.
El paquete no se copia sobre ml/ del proyecto principal. No modifica PH927.
