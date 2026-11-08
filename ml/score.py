"""Aplicar el ICC congelado, sin fit. Retrospectiva descriptiva; reserva sin score.

Un modelo rechazado nunca se promueve automáticamente al cambiar el CSV.
Si revisaron la historia se conserva el modelo y se informa la discrepancia.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ml import baseline as b
from ml.train import score_factor, cargas_admisibles


def validar_modelo(model):
    if model.get('schema')=='icc_pca2_diagnostico_4.2':
        from ml.pca2 import validar_modelo as validar_pca2
        return validar_pca2(model)
    if model.get('schema')=='icc_fa_modelo_4.1':
        from ml.factor import validar_modelo as validar_fa
        return validar_fa(model)
    if model.get('schema')!='icc_s1_modelo_4.0' or b.hash_json(model.get('config_s1'))!=b.hash_json(b.CONFIG_S1):
        raise ValueError('Schema/configuración de modelo incompatible con S1.')
    original={k:v for k,v in model.items() if k not in ('modelo_id','archivos_sha256')}
    if model.get('modelo_id')!=b.hash_json(original)[:20]:
        raise ValueError('Integridad del modelo inválida.')
    b.validar_referencias(model['referencias'])
    dates=model['referencias']['fechas_train']
    if len(dates)!=model['referencias']['n_train'] or len(set(dates))!=len(dates) or dates!=sorted(dates):
        raise ValueError('Fechas de entrenamiento inválidas.')
    if not all(b.CORTES_ICC['train'][0]<=d<=b.CORTES_ICC['train'][1] for d in dates):
        raise ValueError('Muestra entrenada fuera del protocolo.')
    gates=model['gates']
    pca=model['parametros_pca']
    required={'cobertura','economia_baseline','sensibilidad_baseline','variacion_pca'}
    if pca is not None:
        required|={'cargas_pca','economia_pca','perturbaciones_pca','reconstruccion','saturacion'}
        for field in ('cargas','centro_pca','media_y_train','std_y_train'):
            v=np.asarray(pca[field],float)
            if v.shape!=(3,) or not np.isfinite(v).all():raise ValueError('Vector PCA inválido: '+field)
        if (np.asarray(pca['std_y_train'])<=1e-12).any() or pca['sf']<1e-6 or not np.isfinite([pca['f0'],pca['sf']]).all():
            raise ValueError('Escala PCA inválida.')
        if not np.isclose(np.linalg.norm(pca['cargas']),1.,atol=1e-10):raise ValueError('Carga PCA no normalizada.')
        if pca['solver']!='full' or pca['whiten'] or pca['n_components']!=1:raise ValueError('Algoritmo distinto de S1.')
        if gates['cargas_pca']['pasa']!=cargas_admisibles(pca['cargas'])['pasa']:
            raise ValueError('Cargas/decisión inconsistentes.')
    if set(gates)!=required or not all(isinstance(v.get('pasa'),bool) for v in gates.values()):
        raise ValueError('Controles faltantes/invalidos.')
    if not gates['economia_baseline']['pasa'] or not gates['cobertura']['pasa']:
        raise ValueError('Baseline no habilitado.')
    accepted=pca is not None and all(v['pasa'] for v in gates.values())
    if model['pca_aceptado']!=accepted or model['metodo_elegido']!=('pca_s1' if accepted else 'baseline_s1'):
        raise ValueError('Modelo pretende saltar controles.')
    if model['motivos_rechazo_pca']!=[k for k,v in gates.items() if not v['pasa']]:
        # JSON ordena claves al persistir: comparar conjuntos, sin hacer depender decisión del orden.
        if set(model['motivos_rechazo_pca'])!={k for k,v in gates.items() if not v['pasa']}:
            raise ValueError('Motivos de rechazo inconsistentes.')
    if model['parametros_sha256']!=b.hash_json({'referencias':model['referencias'],'pca':pca}):
        raise ValueError('Hash de parámetros incompatible.')
    return model


def cargar_modelo(path):
    path=Path(path)
    model=validar_modelo(json.loads(path.read_text(encoding='utf-8')))
    for name,digest in model.get('archivos_sha256',{}).items():
        if Path(name).name!=name:raise ValueError('Ruta inválida en bundle de modelo.')
        file=path.parent/name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('Bundle de entrenamiento incompleto o alterado: '+name)
    return model


def generar_indice(frame,model):
    if model.get('schema')=='icc_pca2_diagnostico_4.2':
        from ml.pca2 import generar_diagnostico
        return generar_diagnostico(frame,model)
    if model.get('schema')=='icc_fa_modelo_4.1':
        from ml.factor import generar_indice as generar_fa
        return generar_fa(frame,model)
    validar_modelo(model)
    refs=model['referencias']
    result=b.aplicar_baseline_icc(frame,refs)
    mask=result['utilizable_baseline']
    result['factor_pca_diagnostico']=np.nan
    result['icc_pca_candidato']=np.nan
    pca=model['parametros_pca']
    if pca is not None:
        f,_,P=score_factor(frame.loc[mask],refs,pca)
        result.loc[mask,'factor_pca_diagnostico']=f
        if model['gates']['cargas_pca']['pasa']:
            result.loc[mask,'icc_pca_candidato']=P
    result['icc_indice']=result['icc_pca_candidato'] if model['pca_aceptado'] else result['icc_baseline_s1']
    result['metodo_elegido']=model['metodo_elegido']
    result['estado_producto']=model['estado_baseline'] if not model['pca_aceptado'] else 'pca_experimental'
    result['motivos_rechazo_pca']=';'.join(model['motivos_rechazo_pca'])
    result['modelo_id']=model['modelo_id']
    train_mask=b.asignar_splits_icc(frame).eq('train')&b.mascara_core(frame)
    matches=b.hash_bloque(frame.loc[train_mask])==refs['train_sha256']
    result['historia_train_coincide']=matches
    for name,(lo,hi) in refs['rangos_train'].items():
        result['fuera_rango_train_'+name]=frame[name].notna()&(~frame[name].between(lo,hi))
    # Diferencia sobre meses consecutivos del calendario completo; no salta ausencias.
    result['icc_delta_1m_pp']=result['icc_indice'].diff()
    b.validar_baseline_icc(result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--model',type=Path)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    frame,source=b.cargar_entrada(args.root,args.input)
    path=args.model or b.directorio_modelo(args.root,frame)/'entrenamiento'/'modelo_icc.json'
    model=cargar_modelo(path)
    result=generar_indice(frame,model)
    base=b.directorio_modelo(args.root,frame)
    if model.get('schema')=='icc_fa_modelo_4.1':base=base.parent/'v4.1'
    if model.get('schema')=='icc_pca2_diagnostico_4.2':base=base.parent/'v4.2'
    output=args.output_dir or base/('score_'+model['modelo_id'])
    metadata={'schema':'icc_pca2_scoring_4.2' if model.get('schema')=='icc_pca2_diagnostico_4.2' else 'icc_fa_scoring_4.1' if model.get('schema')=='icc_fa_modelo_4.1' else 'icc_s1_scoring_4.0','modelo_id':model['modelo_id'],
              'modelo_archivo_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
              'fuente':source,'historia_train_coincide':bool(result['historia_train_coincide'].all()),
              'cortes':b.CORTES_ICC,'reserva_scoreada':False,'metodo_elegido':model['metodo_elegido']}
    b.publicar_bundle(output,{'icc_indice.csv':result.to_csv(index=False).encode()},'scoring_metadata.json',metadata)
    print(json.dumps({'salida':str(output),'filas_scoreadas':int(result['icc_indice'].notna().sum()),
                      'metodo':model['metodo_elegido']},ensure_ascii=False))


if __name__=='__main__':main()
