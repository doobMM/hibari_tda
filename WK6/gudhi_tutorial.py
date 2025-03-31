#%%
#######################################
########### gudhi test ################
#######################################


import gudhi

def print_simplex(simplex_tree : gudhi.simplex_tree.SimplexTree) :
    result_str = 'Rips complex is of dimension ' + repr(simplex_tree.dimension()) + ' - ' + \
        repr(simplex_tree.num_simplices()) + ' simplices - ' + \
        repr(simplex_tree.num_vertices()) + ' vertices.'
    print(result_str)
    fmt = '%s -> %.2f'
    for filtered_value in simplex_tree.get_filtration():
        print(fmt % tuple(filtered_value))


points = [[1, 1], [7, 0], [4, 6], [9, 6], [0, 14], [2, 19], [9, 17]]
# rips_complex = gudhi.RipsComplex(points=points, max_edge_length=12.0)
rips_complex = gudhi.RipsComplex(points=points, max_edge_length=12.0, sparse=2)

simplex_tree = rips_complex.create_simplex_tree(max_dimension=1)
print_simplex(simplex_tree)

#%%
# same result from different codes 1

cplx = gudhi.RipsComplex(points=points, max_edge_length=12.0).create_simplex_tree(max_dimension=2)
print_simplex(cplx)


#%%
# same result from different codes 2

from scipy.spatial.distance import cdist
distance_matrix = cdist(points, points)
cplx = gudhi.SimplexTree.create_from_array(distance_matrix, max_filtration=12.0)
cplx.expansion(2)
print_simplex(cplx)



#%%
# same result from different codes 3

from scipy.spatial import cKDTree
points = [[1, 1], [7, 0], [4, 6], [9, 6], [0, 14], [2, 19], [9, 17]]
tree = cKDTree(points)
edges = tree.sparse_distance_matrix(tree, max_distance=12.0, output_type="coo_matrix")
cplx = gudhi.SimplexTree()
cplx.insert_edges_from_coo_matrix(edges)
cplx.expansion(2)
print_simplex(cplx)

# This way, you can easily add a call to reduce_graph() before the insertion, 
# use a different metric to compute the matrix, or other variations.




#%%
# Example from a distance matrix

import pandas as pd
import numpy as np

rips_complex = gudhi.RipsComplex(distance_matrix=[[],
                                                  [6.0827625303],
                                                  [5.8309518948, 6.7082039325],
                                                  [9.4339811321, 6.3245553203, 5],
                                                  [13.0384048104, 15.6524758425, 8.94427191, 12.0415945788],
                                                  [18.0277563773, 19.6468827044, 13.152946438, 14.7648230602, 5.3851648071],
                                                  [17.88854382, 17.1172427686, 12.0830459736, 11, 9.4868329805, 7.2801098893]],
                                 max_edge_length=12.0)

simplex_tree = rips_complex.create_simplex_tree(max_dimension=1)
print_simplex(simplex_tree)


#%%
# Example from a correlation matrix

# User defined correlation matrix is:
# |1     0.06    0.23    0.01    0.89|
# |0.06  1       0.74    0.01    0.61|
# |0.23  0.74    1       0.72    0.03|
# |0.01  0.01    0.72    1       0.7 |
# |0.89  0.61    0.03    0.7     1   |
correlation_matrix=np.array([[1., 0.06, 0.23, 0.01, 0.89],
                            [0.06, 1., 0.74, 0.01, 0.61],
                            [0.23, 0.74, 1., 0.72, 0.03],
                            [0.01, 0.01, 0.72, 1., 0.7],
                            [0.89, 0.61, 0.03, 0.7, 1.]], float)

distance_matrix = 1 - correlation_matrix
rips_complex = gudhi.RipsComplex(distance_matrix=distance_matrix, max_edge_length=1.0)

simplex_tree = rips_complex.create_simplex_tree(max_dimension=1)
print_simplex(simplex_tree)

# If you compute the persistence diagram(PD) and 
# convert distances back to correlation values, 
# points in the PD will be under the diagonal, and 
# bottleneck distance and persistence graphical tool will not work properly, 



#%%
# Example from a distance matrix and weights

from gudhi.weighted_rips_complex import WeightedRipsComplex
dist = [[], [1]]
weights = [1, 100]
w_rips = WeightedRipsComplex(distance_matrix=dist, weights=weights)
st = w_rips.create_simplex_tree(max_dimension=2)
print(list(st.get_filtration()))




#%%
# Example from a point cloud combined with DistanceToMeasure

from scipy.spatial.distance import cdist
from gudhi.point_cloud.dtm import DistanceToMeasure
from gudhi.weighted_rips_complex import WeightedRipsComplex
pts = np.array([[2.0, 2.0], [0.0, 1.0], [3.0, 4.0]])
dist = cdist(pts,pts)
dtm = DistanceToMeasure(2, q=2, metric="precomputed")
r = dtm.fit_transform(dist)
w_rips = WeightedRipsComplex(distance_matrix=dist, weights=r)
st = w_rips.create_simplex_tree(max_dimension=2)
print(st.persistence())




#%%
# DTM Rips Complex

from gudhi.dtm_rips_complex import DTMRipsComplex
pts = np.array([[2.0, 2.0], [0.0, 1.0], [3.0, 4.0]])
dtm_rips = DTMRipsComplex(points=pts, k=2)
st = dtm_rips.create_simplex_tree(max_dimension=2)
print(st.persistence())





