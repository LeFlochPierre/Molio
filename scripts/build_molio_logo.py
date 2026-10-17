"""Build the original Molio logo's smooth 3D mesh. Requires NumPy; runtime uses the JSON asset."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
# Rounded M: two small attached feet, two soft shoulders and a distinct ball in the central valley.
CENTRES=np.array([[-1.24,-.76,.04],[-.96,.73,.04],[-.02,-.18,.20],[.98,.76,-.04],[1.28,-.73,.08]])
RADII=np.array([.31,.49,.34,.47,.32])
COLOURS=np.array([[130,220,238],[104,165,242],[181,188,245],[169,144,238],[119,210,199]])/255

def field(p):
    d=np.linalg.norm(p[...,None,:]-CENTRES,axis=-1)-RADII
    parts=[d[...,i] for i in range(len(CENTRES))]
    for a,b,r in [(0,1,.115),(1,2,.105),(2,3,.105),(3,4,.115)]:
        pa=p-CENTRES[a];ba=CENTRES[b]-CENTRES[a]
        h=np.clip(np.sum(pa*ba,axis=-1)/np.dot(ba,ba),0,1)
        parts.append(np.linalg.norm(pa-h[...,None]*ba,axis=-1)-r)
    result=parts[0]
    for other in parts[1:]:
        h=np.clip(.5+.5*(other-result)/.16,0,1)
        result=other*(1-h)+result*h-.16*h*(1-h)
    return result

def main():
    axes=[np.linspace(-1.9,1.9,57),np.linspace(-1.55,1.65,49),np.linspace(-.9,.9,29)]
    grid=np.stack(np.meshgrid(*axes,indexing='ij'),axis=-1);values=field(grid)
    points=grid.reshape(-1,3);values=values.ravel();ids=np.arange(len(points)).reshape(grid.shape[:3])
    vertices=[];faces=[];edges={}
    def vertex(a,b):
        key=tuple(sorted((a,b)))
        if key not in edges:
            f=values[a]/(values[a]-values[b]);edges[key]=len(vertices);vertices.append(points[a]+f*(points[b]-points[a]))
        return edges[key]
    tets=[(0,5,1,6),(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6)]
    for x in range(len(axes[0])-1):
        for y in range(len(axes[1])-1):
            for z in range(len(axes[2])-1):
                cube=[ids[x,y,z],ids[x+1,y,z],ids[x+1,y+1,z],ids[x,y+1,z],ids[x,y,z+1],ids[x+1,y,z+1],ids[x+1,y+1,z+1],ids[x,y+1,z+1]]
                ds=values[cube]
                if np.all(ds>=0) or np.all(ds<0):continue
                for tet in tets:
                    inside=[cube[i] for i in tet if values[cube[i]]<0];outside=[cube[i] for i in tet if values[cube[i]]>=0]
                    if not inside or not outside:continue
                    if len(inside)==1:faces.append([vertex(inside[0],b) for b in outside])
                    elif len(outside)==1:faces.append([vertex(outside[0],a) for a in inside])
                    else:
                        a,b=inside;c,d=outside
                        ac,ad,bc,bd=vertex(a,c),vertex(a,d),vertex(b,c),vertex(b,d)
                        faces.extend([[ac,ad,bc],[ad,bd,bc]])
    vertices=np.array(vertices);faces=np.array(faces)
    normals=np.stack([field(vertices+np.eye(3)[i]*.001)-field(vertices-np.eye(3)[i]*.001) for i in range(3)],axis=-1)
    normals/=np.linalg.norm(normals,axis=-1)[:,None]
    tri=vertices[faces];cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);flip=np.sum(cross*normals[faces].mean(axis=1),axis=1)<0
    faces[flip]=faces[flip][:,[0,2,1]]
    distance=np.linalg.norm(vertices[:,None,:]-CENTRES,axis=-1)-RADII
    weights=np.exp(-5*distance);weights/=weights.sum(axis=-1)[:,None];colours=weights@COLOURS
    data={'description':'Continuous M-shaped Molio sculpture with flexible attached cyan and mint tips. Decorative, not a molecular structure.','vertices':np.round(vertices*10,4).tolist(),'normals':np.round(normals,5).tolist(),'colours':np.round(colours,4).tolist(),'faces':faces.ravel().tolist()}
    path=ROOT/'molecular_lab/web/molio-logo.json';path.write_text(json.dumps(data,separators=(',',':')))
    print(f'{path.name}: {len(vertices)} vertices, {len(faces)} triangles, {path.stat().st_size} bytes')
if __name__=='__main__':main()
