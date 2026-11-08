"""PCA2 ICC 4.2: representación de dos dimensiones, sin agregado escalar ML.

Diagnóstico reproducible con igual core y train. Compara reconstrucción con
PCA1/FA1/B1 (1D) y un comparador predefinido [V, 0.8C+0.2M] (2D).
Ni varianza explicada ni mejor reconstrucción definen favorabilidad económica.
"""
from pathlib import Path
import hashlib
import html
import json

import numpy as np
import pandas as pd
import sklearn
from sklearn.decomposition import PCA

from ml import baseline as b, train as t, factor as fa

VERSION_PCA2='4.2'
CONFIG_PCA2={
    'metodo':'pca2','version':VERSION_PCA2,'adopcion_local':'2026-10-06',
    'config_baseline':b.CONFIG_S1,'n_components':2,'svd_solver':'full','whiten':False,
    'orientacion':'por eje: mayor carga absoluta positiva, sin alterar signo individual',
    'comparador_2d':['V','H=0.80*C+0.20*M'],
    'mejora_reconstruccion_2d_min':.10,'ratio_mse_input_max':1.25,
    'coseno_subespacio_min':.95,'spearman_reconstruccion_min':.90,
    'piso_varianza_pc2':1e-12,'perturbaciones':[.9,1.1],
    'indice_pca2_definido':False,'comparacion':'exploratoria; validacion ya utilizada',
}


def ajustar_factor(Z):
    estimator=PCA(n_components=2,svd_solver='full',whiten=False).fit(Z)
    A=estimator.components_.copy()
    for i in range(2):
        if A[i,np.argmax(np.abs(A[i]))]<0:A[i]*=-1
    return {'cargas':A.tolist(),'centro_pca':estimator.mean_.tolist(),
            'varianza_explicada_ratio':estimator.explained_variance_ratio_.tolist(),
            'varianza_explicada':estimator.explained_variance_.tolist(),
            'n_components':2,'svd_solver':'full','whiten':False}


def proyectar(Z,params):
    return (np.asarray(Z)-np.asarray(params['centro_pca']))@np.asarray(params['cargas']).T


def reconstruir(Z,params):
    return proyectar(Z,params)@np.asarray(params['cargas'])+np.asarray(params['centro_pca'])


def matriz_z(frame,refs,params):
    return (t.transformar(frame,refs)-np.asarray(params['media_y_train']))/np.asarray(params['std_y_train'])


def mse(z,estimated):
    error=((np.asarray(z)-np.asarray(estimated))**2).mean(axis=0)
    return {'por_input':error.tolist(),'promedio':float(error.mean())}


def contraste(error_modelo,error_comparador):
    m=np.asarray(error_modelo['por_input']);c=np.asarray(error_comparador['por_input'])
    usable=bool((c>1e-12).all() and c.mean()>1e-12)
    improvement=float(1-m.mean()/c.mean()) if usable else None
    ratios=(m/c).tolist() if usable else None
    return {'pasa':bool(usable and improvement>=.10 and np.all(m/c<=1.25)),
            'mejora_promedio':improvement,'ratios_por_input':ratios,
            'motivo':'comparador con error nulo; inconcluso' if not usable else ''}


def comparadores(train,val,refs,params):
    Z=matriz_z(train,refs,params);Zv=matriz_z(val,refs,params)
    V,C,M,B=b.componentes(train[b.STOCK_REAL],train[b.TASA],train[b.G3],refs)
    Vv,Cv,Mv,Bv=b.componentes(val[b.STOCK_REAL],val[b.TASA],val[b.G3],refs)
    X1=np.column_stack([np.ones(len(train)),B]);X1v=np.column_stack([np.ones(len(val)),Bv])
    X2=np.column_stack([np.ones(len(train)),V,.8*C+.2*M])
    X2v=np.column_stack([np.ones(len(val)),Vv,.8*Cv+.2*Mv])
    coef1=np.linalg.lstsq(X1,Z,rcond=None)[0];coef2=np.linalg.lstsq(X2,Z,rcond=None)[0]
    p1=t.ajustar_factor(Z);f1=fa.ajustar_factor(Z)
    A1=np.asarray(p1['cargas']);L1=np.asarray(f1['cargas'])
    fitted={
        'baseline_1d':(X1@coef1,X1v@coef1,1),
        'pca1':(np.outer(t.proyectar(Z,p1),A1)+p1['centro_pca'],
                np.outer(t.proyectar(Zv,p1),A1)+p1['centro_pca'],1),
        'fa1':(np.outer(t.proyectar(Z,f1),L1)+f1['centro_factor'],
               np.outer(t.proyectar(Zv,f1),L1)+f1['centro_factor'],1),
        'comparador_2d_V_H':(X2@coef2,X2v@coef2,2),
        'pca2':(reconstruir(Z,params),reconstruir(Zv,params),2),
    }
    metrics={name:{'dimensiones':dim,'train':mse(Z,fit),'validacion':mse(Zv,apply)}
             for name,(fit,apply,dim) in fitted.items()}
    comparison=contraste(metrics['pca2']['validacion'],metrics['comparador_2d_V_H']['validacion'])
    rank=int(np.linalg.matrix_rank(X2))
    if rank!=3:comparison.update(pasa=False,motivo='comparador 2D no identificable')
    n=len(val)//2
    blocks=[]
    for start,end in [(0,n),(n,len(val))]:
        block={name:mse(Zv[start:end],apply[start:end]) for name,(_,apply,_) in fitted.items()}
        blocks.append({'desde':val['fecha_mes'].iloc[start],'hasta':val['fecha_mes'].iloc[end-1],
                       'n':end-start,'errores':block,
                       'contraste_2d':contraste(block['pca2'],block['comparador_2d_V_H'])})
    return {'pasa':comparison['pasa'],'metricas':metrics,'contraste_2d':comparison,
            'contraste_baseline_1d_descriptivo':contraste(metrics['pca2']['validacion'],metrics['baseline_1d']['validacion']),
            'bloques_validacion_descriptivos':blocks,
            'comparador_2d_rango_diseno':rank,
            'coeficientes_baseline_1d_train':coef1.tolist(),'coeficientes_comparador_2d_train':coef2.tolist(),
            'nota':'PCA2 y V/H conservan 2 dimensiones; las comparaciones 1D son descriptivas. Reconstruccion no valida un ICC.'}


def cosenos_subespacios(A,B):
    """Cosenos de ángulos principales; invariante a signos/rotaciones internas."""
    Qa=np.linalg.qr(np.asarray(A).T)[0];Qb=np.linalg.qr(np.asarray(B).T)[0]
    return np.clip(np.linalg.svd(Qa.T@Qb,compute_uv=False),0,1)


def perturbaciones(train,val,refs,params):
    Z=matriz_z(train,refs,params);Zv=matriz_z(val,refs,params)
    base=np.asarray(params['cargas']);default=reconstruir(Zv,params);cases=[]
    for j in range(3):
        for multiplier in (.9,1.1):
            D=np.ones(3);D[j]=multiplier
            alt=ajustar_factor(Z*D)
            # La función de compresión sobre Z original usa (A_pert * D).
            mapped=np.asarray(alt['cargas'])*D
            cos=cosenos_subespacios(base,mapped)
            reconstruction=reconstruir(Zv*D,alt)/D
            correlations=[t.rho(default[:,i],reconstruction[:,i]) for i in range(3)]
            identified=alt['varianza_explicada'][1]>1e-12
            cases.append({'columna':['volumen','costo','momentum'][j],'multiplicador':multiplier,
                          'cosenos_angulos_principales':cos.tolist(),
                          'spearman_reconstruccion_val':correlations,
                          'pasa':bool(identified and cos.min()>=.95 and all(c is not None and c>=.90 for c in correlations))})
    return {'pasa':all(x['pasa'] for x in cases),'casos':cases,
            'nota':'Comparar subespacio/reconstruccion; no comparar ejes por nombre ni rankings de un indice inexistente.'}


def entrenar_icc(frame,source=None):
    refs=b.ajustar_referencias_icc(frame)
    split=b.asignar_splits_icc(frame);core=b.mascara_core(frame)
    train=frame.loc[split.eq('train')&core];val=frame.loc[split.eq('validacion')&core]
    if len(val)<18:raise ValueError('Validacion insuficiente: mínimo 18 meses.')
    economics=b.controles_economicos(refs)
    if not economics['pasa']:raise ValueError('Baseline no pasa escenarios económicos.')
    Y=t.transformar(train,refs);mean=Y.mean(axis=0);std=Y.std(axis=0,ddof=0)
    gates={'cobertura':{'pasa':True,'n_train':len(train),'n_validacion':len(val)},
           'economia_baseline':economics,'sensibilidad_baseline':t.sensibilidades_baseline(train,val,refs),
           'variacion_inputs':{'pasa':bool(np.isfinite(std).all() and (std>1e-12).all()),'std_y_train':std.tolist()}}
    params=None
    if gates['variacion_inputs']['pasa']:
        params={**ajustar_factor((Y-mean)/std),'media_y_train':mean.tolist(),'std_y_train':std.tolist()}
        gates['dos_dimensiones_identificables']={'pasa':params['varianza_explicada'][1]>1e-12}
        if gates['dos_dimensiones_identificables']['pasa']:
            gates['reconstruccion_2d']=comparadores(train,val,refs,params)
            gates['perturbaciones_subespacio']=perturbaciones(train,val,refs,params)
    model={'schema':'icc_pca2_diagnostico_4.2','config_pca2':CONFIG_PCA2,'referencias':refs,
           'protocolo':b.comprobar_protocolo_icc(frame),'fuente':source or {'fuentes_reconstruidas':False},
           'parametros_pca2':params,'controles_diagnosticos':gates,
           'controles_diagnosticos_pasan':bool(all(x['pasa'] for x in gates.values())),
           'indice_pca2_definido':False,'pca2_admitido_como_icc':False,
           'metodo_elegido':'baseline_s1','motivo_no_generar_indice_pca2':'No se definio agregacion economica 2D->1D; reconstruccion no equivale a favorabilidad.',
           'estado_baseline':'experimental' if gates['sensibilidad_baseline']['pasa'] else 'experimental_sensible',
           'estado_producto':'diagnostico_pca2','disponibilidad_historica_verificada':False,
           'validacion_sha256':b.hash_bloque(val),
           'entorno':{**b.runtime_metadata(),'scikit_learn':sklearn.__version__},
           'codigo_sha256':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                            for name in ('baseline.py','train.py','score.py','factor.py','pca2.py')},
           'limitaciones':['PCA2 genera dos proyecciones, no un unico indice ni probabilidad de acceso.',
                           'Signos de ejes son convenciones; no orientacion economica de favorabilidad.',
                           'La comparacion con 1D favorece mayor dimensionalidad; V/H es comparador 2D predefinido.',
                           'Validacion ya observada en PCA1/FA1; comparacion exploratoria, sin test independiente.',
                           'Stock y tasa son proxies de poblaciones distintas; no hay vintages verificados.',
                           'Retrospectiva posterior a la decision; reserva sin score; uso operativo no habilitado.']}
    model['parametros_sha256']=b.hash_json({'referencias':refs,'pca2':params})
    model['modelo_id']=b.hash_json(model)[:20]
    return model,generar_diagnostico(frame,model,roles=('train','validacion'))


def validar_modelo(model):
    if model.get('schema')!='icc_pca2_diagnostico_4.2' or b.hash_json(model.get('config_pca2'))!=b.hash_json(CONFIG_PCA2):
        raise ValueError('Configuración PCA2 incompatible.')
    original={k:v for k,v in model.items() if k not in ('modelo_id','archivos_sha256')}
    if model.get('modelo_id')!=b.hash_json(original)[:20]:raise ValueError('Integridad PCA2 inválida.')
    refs=model['referencias'];b.validar_referencias(refs)
    dates=refs['fechas_train']
    if (len(dates)!=refs['n_train'] or len(set(dates))!=len(dates) or dates!=sorted(dates)
        or not all(b.CORTES_ICC['train'][0]<=d<=b.CORTES_ICC['train'][1] for d in dates)):
        raise ValueError('Muestra PCA2 fuera del protocolo.')
    if model['indice_pca2_definido'] or model['pca2_admitido_como_icc'] or model['metodo_elegido']!='baseline_s1':
        raise ValueError('PCA2 no tiene agregado ICC aprobado.')
    params=model['parametros_pca2'];gates=model['controles_diagnosticos']
    required={'cobertura','economia_baseline','sensibilidad_baseline','variacion_inputs'}
    if params is not None:
        A=np.asarray(params['cargas'],float);center=np.asarray(params['centro_pca'],float)
        if A.shape!=(2,3) or center.shape!=(3,) or not np.isfinite(A).all() or not np.isfinite(center).all():
            raise ValueError('Vectores PCA2 inválidos.')
        if not np.allclose(A@A.T,np.eye(2),atol=1e-12):raise ValueError('Ejes PCA2 no ortonormales.')
        for key in ('media_y_train','std_y_train'):
            x=np.asarray(params[key],float)
            if x.shape!=(3,) or not np.isfinite(x).all():raise ValueError('Escala PCA2 inválida.')
        if (np.asarray(params['std_y_train'])<=1e-12).any():raise ValueError('Escala PCA2 constante.')
        explained=np.asarray(params['varianza_explicada_ratio'],float);variance=np.asarray(params['varianza_explicada'],float)
        if (explained.shape!=(2,) or variance.shape!=(2,) or not np.isfinite([explained,variance]).all()
                or (explained<0).any() or explained.sum()>1+1e-10 or (variance<0).any()):
            raise ValueError('Varianza PCA2 inválida.')
        if params['n_components']!=2 or params['svd_solver']!='full' or params['whiten']:
            raise ValueError('Algoritmo PCA2 distinto del acordado.')
        required.add('dos_dimensiones_identificables')
        identified=variance[1]>1e-12
        if gates['dos_dimensiones_identificables']['pasa']!=identified:raise ValueError('Identificación PCA2 inconsistente.')
        if identified:required|={'reconstruccion_2d','perturbaciones_subespacio'}
    if set(gates)!=required or not all(isinstance(v.get('pasa'),bool) for v in gates.values()):
        raise ValueError('Controles PCA2 faltantes o inválidos.')
    if not gates['cobertura']['pasa'] or not gates['economia_baseline']['pasa']:raise ValueError('Baseline no habilitado.')
    if model['controles_diagnosticos_pasan']!=all(x['pasa'] for x in gates.values()):
        raise ValueError('Decisión diagnóstica inconsistente.')
    if model['parametros_sha256']!=b.hash_json({'referencias':refs,'pca2':params}):
        raise ValueError('Hash de parámetros PCA2 incompatible.')
    return model


def generar_diagnostico(frame,model,roles=None):
    validar_modelo(model)
    refs=model['referencias'];out=b.aplicar_baseline_icc(frame,refs,roles)
    usable=out['utilizable_baseline'];params=model['parametros_pca2']
    out['pc1_diagnostico']=np.nan;out['pc2_diagnostico']=np.nan
    if params is not None and model['controles_diagnosticos']['dos_dimensiones_identificables']['pasa']:
        F=proyectar(matriz_z(frame.loc[usable],refs,params),params)
        out.loc[usable,'pc1_diagnostico']=F[:,0];out.loc[usable,'pc2_diagnostico']=F[:,1]
    out['icc_indice']=out['icc_baseline_s1'];out['indice_pca2_definido']=False
    out['metodo_elegido']='baseline_s1';out['version_modelo']=VERSION_PCA2
    out['estado_producto']=model['estado_baseline'];out['modelo_id']=model['modelo_id']
    out['estado_pca2']='diagnostico_sin_agregacion_icc'
    train=frame.loc[b.asignar_splits_icc(frame).eq('train')&b.mascara_core(frame)]
    out['historia_train_coincide']=b.hash_bloque(train)==refs['train_sha256']
    for feature,(lo,hi) in refs['rangos_train'].items():
        out['fuera_rango_train_'+feature]=frame[feature].notna()&(~frame[feature].between(lo,hi))
    out['icc_delta_1m_pp']=out['icc_indice'].diff();b.validar_baseline_icc(out)
    return out


def render_informe(model,frame):
    def fmt(x):
        return f'{x:.4f}' if isinstance(x,float) else html.escape(str(x))
    def table(headers,rows):
        return '<table><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+fmt(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'
    controls=model['controles_diagnosticos'];params=model['parametros_pca2']
    parts=['<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ICC — PCA2</title>',
           '<style>body{font:17px system-ui;max-width:1080px;margin:40px auto;padding:0 24px;color:#142a38}table{border-collapse:collapse;width:100%;margin:20px 0}td,th{border:1px solid #ccd;padding:10px;text-align:left}h1,h2{color:#175a72}svg{width:100%;height:auto}</style>',
           '<h1>ICC: PCA de dos componentes</h1><p>Representación bidimensional experimental. No se definió un agregado PCA2→ICC. '
           'El índice publicado sigue con baseline S1.</p>',
           '<h2>Qué se compara</h2><p>Mismos 60 meses train, 22 de validación, core R/g3/r y referencias S1. '
           'PCA2 full sin whitening ni búsqueda. Retrospectiva y reserva no deciden el experimento. '
           'Se compara con PCA1/FA1/B1 descriptivamente y con un comparador de dos dimensiones: volumen V y costo/dinámica H=0,80C+0,20M. '
           'Las rectas de reconstrucción de cada input se ajustan solo en train. V/H y PCA2 retienen dos dimensiones con funciones y complejidad distintas; no son familias equivalentes. Mejorar contra una sola dimensión no basta para justificar dos.</p>',
           '<h2>Controles diagnósticos</h2>',table(['Control','Resultado'],[(k,'PASA' if x['pasa'] else 'FALLA') for k,x in controls.items()])]
    if params is not None:
        parts+=['<h2>Componentes aprendidos</h2>',
                table(['Eje','Carga volumen','Carga costo','Carga momentum','Varianza explicada (%)'],[
                    (f'PC{i+1}',*params['cargas'][i],100*params['varianza_explicada_ratio'][i]) for i in range(2)]),
                '<p>Varianza explicada total: '+fmt(100*float(sum(params['varianza_explicada_ratio'])))+'%. '
                'Cada signo se fija solo para reproducibilidad. PC1 y PC2 son ejes estadísticos; una carga negativa de un eje no prueba que menor stock sea favorable. '
                'No se aplican mínimos de cargas de un índice escalar a cada eje de un espacio ortogonal.</p>']
        if 'reconstruccion_2d' in controls:
            reconstruction=controls['reconstruccion_2d'];metrics=reconstruction['metricas']
            parts+=['<h2>Reconstrucción en validación</h2>',
                    table(['Representación','Dimensiones','MSE volumen','MSE costo','MSE momentum','MSE promedio'],[
                        (k,x['dimensiones'],*x['validacion']['por_input'],x['validacion']['promedio']) for k,x in metrics.items()]),
                    '<p>PCA2 contra V/H 2D: mejora promedio '+(fmt(100*reconstruction['contraste_2d']['mejora_promedio'])+'%' if reconstruction['contraste_2d']['mejora_promedio'] is not None else 'inconclusa')+
                    '; ratios por input '+fmt(reconstruction['contraste_2d']['ratios_por_input'])+'. '
                    'Regla previa: mejora ≥10% y ningún ratio >1,25. La métrica está en unidades Z de train, no pesos ni tasa de acceso.</p>',
                    '<h2>Perturbaciones del subespacio</h2>',
                    table(['Columna','Multiplicador','Cosenos principales','Rho reconstrucción V/C/M','Resultado'],[
                        (x['columna'],x['multiplicador'],x['cosenos_angulos_principales'],x['spearman_reconstruccion_val'],x['pasa'])
                        for x in controls['perturbaciones_subespacio']['casos']]),
                    '<p>Se comparan planos y reconstrucciones; cambios de signo o rotación no cambian el subespacio. '
                    'No se mide ranking de un ICC PCA2 inexistente.</p>']
    points=frame.loc[frame['pc1_diagnostico'].notna(),['pc1_diagnostico','pc2_diagnostico','split_temporal']]
    if not points.empty:
        x=points['pc1_diagnostico'];y=points['pc2_diagnostico'];xlo,xhi=float(x.min()),float(x.max());ylo,yhi=float(y.min()),float(y.max())
        def position(v,lo,hi,width):return (float(v)-lo)/max(hi-lo,1e-12)*width
        circles=''.join(f'<circle cx="{80+position(row.pc1_diagnostico,xlo,xhi,720):.2f}" cy="{330-position(row.pc2_diagnostico,ylo,yhi,260):.2f}" r="4" fill="'+('#187798' if row.split_temporal=='train' else '#cf6e29')+'"/>' for row in points.itertuples())
        parts+=['<h2>Proyecciones: train y validación</h2><svg viewBox="0 0 880 410" role="img" aria-label="PCA2: azul train, naranja validación">'
                '<path d="M80 60 V330 H800" fill="none" stroke="#888"/>'+circles+
                f'<text x="80" y="355">{xlo:.2f}</text><text x="750" y="355">{xhi:.2f}</text><text x="15" y="75">{yhi:.2f}</text><text x="15" y="330">{ylo:.2f}</text>'
                '<text x="420" y="385">PC1</text><text x="15" y="40">PC2</text></svg><p>Azul: train. Naranja: validación. '
                'Proyecciones adimensionales. El cambio de región muestra drift descriptivo, no regímenes económicos etiquetados.</p>']
    parts+=['<h2>Qué falta para un único índice</h2><p>Definir una agregación económicamente interpretable de PC1/PC2, '
            'ajustada sin usar validación para elegir pesos y comprobada con los escenarios ya acordados. '
            'No sumar ejes ni ponderarlos por varianza explicada automáticamente: conservar varianza no equivale a favorabilidad. '
            'Mientras eso no esté definido, el artefacto solo aplica PCs como diagnóstico y mantiene el índice B.</p>',
            '<h2>Alcance</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in model['limitaciones'])+'</ul>',
            '<p>Fuentes reconstruidas: '+str(model['fuente'].get('fuentes_reconstruidas',False))+'. Modelo '+model['modelo_id']+'.</p></html>']
    return ''.join(parts)


def exportar_entrenamiento(model,frame,output):
    return b.publicar_bundle(output,{'icc_pca2_diagnostico.csv':frame.to_csv(index=False).encode(),
                                    'informe_pca2.html':render_informe(model,frame).encode()},
                            'modelo_pca2.json',model)
