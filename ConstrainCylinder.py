"""
Auteur : Paul Chaillou
Contact : paul.chaillou@inria.fr
Année : 2024
Propriétaire : Université de Lille - CNRS 
License : Non définie, mais développé dans une démarche Open-Source et Logiciel Libre avec volonté de partage et de travail collaboratif. Développé dans un but non-marchand, en cas d'utilisation commerciale, merci de minimiser les prix et de favoriser le partage gratuit de tout ce qui peut l'être. A utiliser dans des buts prenant en compte les questions éthiques et morales (si possible non-militaire, ne rentrant pas dans le cadre de compétition, de monopole, ou de favorisation d'interets privés).
"""

 # coding=utf-8

import Sofa
import Sofa.constants.Key as Key
import array
import numpy as np
from splib3.topology import remeshing as rf
from stl import mesh
from math import sin,cos, sqrt, acos, radians, dist, ceil
import math
import time

import ConstrainCylinder_Functions as constrain

ELONGATION = False # True = modèle McKibben en élongation, sinon False, en compression


class PressureController(Sofa.Core.Controller): # TODO : ATTENTION : avec le dyn_flag, la pression max, min, et le pas sont multipié par dt. On redivise par dt pour les pressions soient bonnes à l'affichage. Tout est juste, mais du pint de vue du composant, tout est divisé en 2 (la moitié dans stiff_module, l'autre dans le composant = Pas cool, il faudrait mieux factoriser pour rendre le composant réutilisable)
    """
        FR :
        Fonction pour pouvoir modifier les pressions appliqués par le clavier
            INPUT : 
            pas = step, incrément en pression (kPa) à chaque frappe de clavier
            module = variable stiff qui contient toutes les données du robot
            parent = noeud parent des cavités pour s'y connecter

        EN :
        Function to be able to modify the pressures applied by the keyboard
             INPUT:
             pas = step, increment in pressure (kPa) with each keystroke
             module = variable stiff which contains all the data of the robot
             parent = parent node of the cavities to connect them

        Exemple : rootNode.addObject(StiffController(pas=pas,module = stiff,parent = stiff_flop))
    """

    def __init__(self,pas,parent,node2 = "null",*args, **kwargs):

            Sofa.Core.Controller.__init__(self,args,kwargs)

            self.pressure = parent.getObject('SPC')
            self.flag = 0;
            self.pas = pas
            self.max_pression = 300
            

    def onKeypressedEvent(self,e):
    
            pressureValue = self.pressure.value.value[0]

            if e["key"] == Key.A:
                pressureValue += self.pas
                # print('===========D')
                if pressureValue > self.max_pression:
                    pressureValue= self.max_pression
            if e["key"] == Key.Q:
                pressureValue -= self.pas
                if pressureValue < 0:
                    pressureValue = 0
                        
            self.pressure.value =  [pressureValue]
            print('Pression cavité ', pressureValue)        


def createCavity(parent,name_c,i,cavity_model,act_flag): # for v1 -------

    """
    name__c : name of the created node
    i : cavity number
    cavity_model : cavity model filename (should be .stl)
    act_flag = 0 : Inverse Control
    act_flag = 1 : Direct Control

    """
    bellowNode = parent.addChild(name_c+str(i+1))
    MeshLoad = bellowNode.addObject('MeshSTLLoader', filename=cavity_model, flipNormals='0', triangulate='true', name='meshLoader',rotation=[0,0,0], translation=[0, 0,0])#, rotation=[self.ang_dec*self.i_cavity,0,0] if pre-rotated 3D model
    MeshLoad.init()
    points  = MeshLoad.position.value
    triangles = MeshLoad.triangles.value
    bellowNode.addObject('MeshTopology', src='@meshLoader', name='Cavity')
    bellowNode.addObject('MechanicalObject', name='chambreA'+str(i+1),rotation=[0, 0 , 0])#,translation = [0,0,h_module*i]) # 90 on y
    bellowNode.addObject('TriangleCollisionModel', moving='0', simulated='1')
    bellowNode.addObject('TriangleFEMForceField', template='Vec3', name='FEM', method='large', poissonRatio=0.49,  youngModulus=100, thickness = 5) # stable youngModulus = 500 / réel ? = 103
    bellowNode.addObject('UniformMass', totalMass=1000, rayleighMass = 0)

    if act_flag == 0 :
        bellowNode.addObject('SurfacePressureActuator', name='SPC', template = 'Vec3d',triangles='@chambreAMesh'+str(i+1)+'.triangles',minPressure = 0,maxPressure = 300)#,maxPressureVariation = 20)#,valueType=self.value_type)
    elif  act_flag == 1 :
        bellowNode.addObject('SurfacePressureConstraint', name='SPC', triangles='@chambreAMesh'+str(i+1)+'.triangles', value=0,minPressure = 0,maxPressure = 300, valueType="pressure" )#,maxPressureVariation = 20)#,

    bellowNode.init()
    BaseBox = bellowNode.addObject('BoxROI', name='boxROI_base', box=[-8, -8, -1, 8, 8, 1], drawBoxes=True, strict=False,drawTetrahedra = False) # si autom complète, mettre 8 dépendant des dimensions du robot
    BaseBox.init()
    print("selected : ")
    print(BaseBox.indices.value)
    bellowNode.addObject('RestShapeSpringsForceField', points=BaseBox.indices.value, angularStiffness=1e5, stiffness=1e5) # pour accrocher la base du robot dans l'espace

    return bellowNode

def createScene(rootNode):

    # rootNode.addObject('AddPluginRepository', path = '/home/pchaillo/Documents/10-SOFA/sofa/build/master/external_directories/plugins/SoftRobots/lib/') #libSoftRobots.so 1.0
    # rootNode.addObject('AddPluginRepository', path = '/home/pchaillo/Documents/10-SOFA/sofa/build/master/external_directories/plugins/ModelOrderReduction/lib/') #libSoftRobots.so 1.0
    # rootNode.addObject('AddPluginRepository', path = '/home/pchaillo/Documents/10-SOFA/sofa/build/master/external_directories/plugins/BeamAdapter/lib')#/libBeamAdapter.so 1.0

    # required plugins:
    pluginNode  = rootNode.addChild('pluginNode')
    pluginNode.addObject('RequiredPlugin', name='SoftRobots.Inverse') # Where is SofaValidation ? => Deprecated Error in terminal
    pluginNode.addObject('RequiredPlugin', name='SoftRobots')
    pluginNode.addObject('RequiredPlugin', name='BeamAdapter')
    pluginNode.addObject('RequiredPlugin', name='SOFA.Component.IO.Mesh')
    pluginNode.addObject('RequiredPlugin', name='SOFA.Component.Engine.Generate')
    pluginNode.addObject('RequiredPlugin', name='SOFA.Component.Mass')
    pluginNode.addObject('RequiredPlugin', name='SOFA.Component.LinearSolver.Direct')
    pluginNode.addObject('RequiredPlugin', name='SOFA.Component.Constraint.Lagrangian.Correction')  
    pluginNode.addObject('RequiredPlugin', name='Sofa.GL.Component.Rendering3D') 
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Diffusion')
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.AnimationLoop') # Needed to use components [FreeMotionAnimationLoop]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Collision.Geometry') # Needed to use components [SphereCollisionModel]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Constraint.Lagrangian.Correction') # Needed to use components [GenericConstraintCorrection,UncoupledConstraintCorrection]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Constraint.Lagrangian.Solver') # Needed to use components [GenericConstraintSolver]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Engine.Generate') # Needed to use components [ExtrudeQuadsAndGenerateHexas]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Engine.Select') # Needed to use components [BoxROI]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.IO.Mesh') # Needed to use components [MeshOBJLoader]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.LinearSolver.Direct') # Needed to use components [SparseLDLSolver]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.LinearSolver.Iterative') # Needed to use components [CGLinearSolver]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Mass') # Needed to use components [UniformMass]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.ODESolver.Backward') # Needed to use components [EulerImplicitSolver]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Setting') # Needed to use components [BackgroundSetting]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.SolidMechanics.FEM.Elastic') # Needed to use components [HexahedronFEMForceField]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.SolidMechanics.Spring') # Needed to use components [RestShapeSpringsForceField]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.StateContainer') # Needed to use components [MechanicalObject]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Topology.Container.Dynamic') # Needed to use components [HexahedronSetTopologyContainer,TriangleSetTopologyContainer]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Topology.Container.Grid') # Needed to use components [RegularGridTopology]  
    pluginNode.addObject('RequiredPlugin', name='Sofa.Component.Visual') # Needed to use components [VisualStyle]  


    rootNode.findData('gravity').value=[0, 0, 0];
    # rootNode.findData('gravity').value=[0, 0, 0];

    #visual dispaly
    rootNode.addObject('VisualStyle', displayFlags='showVisualModels showBehaviorModels showCollisionModels hideBoundingCollisionModels showForceFields showInteractionForceFields hideWireframe')
    rootNode.addObject('BackgroundSetting', color='0 0.168627 0.211765')

    rootNode.addObject('OglSceneFrame', style="Arrows", alignment="TopRight") # ne marche pas sans GUI
    
    rootNode.findData('dt').value= 0.01;
    
    rootNode.addObject('FreeMotionAnimationLoop')
    rootNode.addObject('DefaultVisualManagerLoop')    

    rootNode.addObject('GenericConstraintSolver', maxIterations='100', tolerance = '0.0000001')

    fichier =  'cylinder_16_parts.stl' 
    # fichier =  'parametric_cavity_sliced2.stl'

    bellowNode = createCavity(parent=rootNode,name_c="cavity",i=1,cavity_model=fichier,act_flag=1)

    points = rootNode.cavity2.meshLoader.position.value

    if ELONGATION == False :
        constrain.ConstrainCavity(points = points,parent=bellowNode,axis = 0,tolerance = 0.2)
        constrain.ConstrainCavity(points = points,parent=bellowNode,axis = 1,tolerance = 0.2)
    else :
    ## Elongation
        constrain.ConstrainCavity(points = points,parent=bellowNode,axis = 2,tolerance = 0.2)

    bellowNode.addObject('SparseLDLSolver', name='ldlsolveur',template="CompressedRowSparseMatrixMat3x3d")
    bellowNode.addObject('GenericConstraintCorrection')
    bellowNode.addObject('EulerImplicitSolver', firstOrder='1', vdamping=0)

    rootNode.addObject(PressureController(pas=10,parent = bellowNode))


    # return rootNode