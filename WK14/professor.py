


# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------- 250414 교수님 barcoe 함수---------------------------- #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #


# 이 부분은 지속성 호몰로지를 계산하는 함수로 오론쯕 행렬의 각 행이 선형 독립이 되게 하고 
# 각 행의 마지막 열이 0이 안 될 때까지 계산을 지속합니다. 
# 이 알고리즘은 매우 technical 하기 때문에 이해할 필요는 없습니다. 계산을 위해 사용하고 
# 음악 분석을 위해서 cycle과 barcode를 계산하기 위한 알고리즘이라고 생각하면 되겠습니다. 
# from pHcol import *

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import itertools as it
import time, random
import os
import datetime
from music21 import stream, note, tempo, chord, clef, meter, instrument # environment, duration, midi, 


# 순환호출 이슈로 다른 파일에 있는 것을 똑같이 가져온 것들 :
################ notes_to_score_xml(process)
################ get_now(util)

def get_now(format : str = "%Y%m%d_%H%M%S"):

    timestamp = datetime.datetime.now().strftime(format) 
    
    return timestamp

def distancesOfMatrix(mat):
    o = []
    for (i,j) in it.combinations_with_replacement(range(len(mat)), 2):
        o.append(mat[i,j])
    o = sorted(list(set(o)))
    if o[0] == 0: # It does not count 0 distance.
        return o[1:]
    return o
#
# INPUT: truncate given sorted list L of floats with start and end.
# OUTPUT: a list of floats.
def truncatedList(L, start, end):
    try: # check start number and end number.
        if start > end:
            return # return None
    except:
        return # return None
    # get start index
    startIndex = 0
    for e, i in enumerate(L):
        if i >= start and i != 0: # It does not count 0 distance.
            startIndex = e
            break
    # get end index.
    endIndex = 0
    for e, i in enumerate(L):
        if i == end:
            endIndex = e
            break
        elif i > end:
            endIndex = e-1
            break
    if endIndex == 0:
        endIndex = len(L)-1
    # check start index and end index.
    if startIndex > endIndex:
        return # return None
    return L[startIndex:endIndex+1]
#
# INPUT: numpy matrix as distance matrix.
# OUTPUT: a list of floats.
def generateFiltrationTimes(mat, numOfDivision = 1000, start = 0, end = 3, exactStep = False, truncate = True, increment = 1e-05, division = True):
    if type(numOfDivision) != int or numOfDivision < 1:
        return # return None
    # for listing filtration times.
    if exactStep == False:
        if truncate == False: # this case requires input value of 'increment'.
            start = mat.min()
            end = mat.max()
        if division == True: # this case requires input values of 'numOfDivision', 'start', 'end'.
            increment = (end-start)/numOfDivision
            print("came here")
        o = [start] # o is for a list of steps of filtration.
        while True:
            if o[-1] < end:
                o.append(o[-1] + increment)
            else:
                break
        o = truncatedList(o,start,end)
    elif exactStep == True:
        o = distancesOfMatrix(mat)
        if truncate == True: # this case requires input value of 'start' and 'end'
            o = truncatedList(o,start,end)
        elif truncate == False: # this case does not require any values of 'start', 'end', 'numOfDivision', 'increment'.
            pass
        else:
            return # return None
    return o
#
# INPUT: list of [step, listOfSimplex].
def generateBoundaryMatrix(listOfSimplexWithStep, dim = [1,2]):
    columnLabelOfSimplexWithStep = []
    columnLabelOfSimplex = []
    columnLabelOfSimplexIndexDic = {}
    stime = time.time()
    num = -1
    for step, listOfSimplex in listOfSimplexWithStep:
        for simplex in listOfSimplex:
            num += 1
            columnLabelOfSimplexWithStep.append([step, simplex])
            columnLabelOfSimplex.append(simplex)
            columnLabelOfSimplexIndexDic[simplex] = num
    stime = time.time()
    matrixElements = []
#     print("columnLabelOfSimplexStart")
    cl = len(columnLabelOfSimplex)
    for e, simplex in enumerate(columnLabelOfSimplex):
        if e % 10000 == 0:
            if e != 0:
#                 print("$",e,"eofl",cl,time.time()-stime,'seconds')
                stime = time.time()
        if len(simplex) - 2 not in dim:
            matrixElements.append([[-1],[-1]]) # -1 is convention.
            continue
        tempr = []
        tempv = {}
        for e, boundary in enumerate(it.combinations(simplex, len(simplex)-1)):
            rowIndexOfElement = columnLabelOfSimplexIndexDic[boundary]
            tempr.append(rowIndexOfElement)
            tempv[rowIndexOfElement] = (-1)**(e+1)
        matrixElements.append([tempr,tempv])
#     print("columnLabelOfSimplexTotal",time.time()-stime,'seconds')
    return [matrixElements, columnLabelOfSimplexWithStep]
#
# INPUT: a list of matrix element for boundary matrix D.
# OUTPUT: R and V matrix from R = DV.
def pHcolGenerateRVmatrix(D, columnLabelOfSimplex, listOfDimensionInput = [1], annotate = True, onlyFiniteInterval = False, birthDeathSimplex = True, sortDimension = False):
    l = len(D)
    o = []
    births = []
    finiteBirths = []
    columnLabelOfSimplexList = [i[1] for i in columnLabelOfSimplex]
    stime = time.time()
#     print('phColOperationStart')
    astime = time.time()
    V = {} # For V matrix.
    lowRindex = []
    lowRindexInd = {}
    lowRvalueDic = {}
    j = 0
    columnInfoj = D[j]
    rowlistj = columnInfoj[0]
    vlistj = columnInfoj[1]
    if rowlistj == [] or max(rowlistj) == -1:
        lowRindex.append(-1) # -1 is convention.
        births.append(j)
    else:
        jr = max(rowlistj)
        finiteBirths.append(jr)
        jc = vlistj[jr]
        lowRindex.append(jr)
        lowRindexInd[jr] = j
        lowRvalueDic[jr] = jc
    # Start
    if birthDeathSimplex:
        if annotate:
            barcodetitle = '-------------------------\n Barcode Start. read as [Dimension, [Birth time, Birth simplex], [Death time, Death simplex], Generators]\n-------------------------\n-------------------------'
        else:
            barcodetitle = '-------------------------\n Barcode Start. read as [Dimension, [Birth time, Birth simplex], [Death time, Death simplex]]\n-------------------------\n-------------------------'
    else:
        if annotate:
            barcodetitle = '-------------------------\n Barcode Start. read as [Dimension, [Birth time, Death time], Generators]\n-------------------------\n-------------------------'
        else:
            barcodetitle = '-------------------------\n Barcode Start. read as [Dimension, [Birth time, Death time]]\n-------------------------\n-------------------------'
    # if not sortDimension:
        # print(barcodetitle)
    for e in range(1,l):
        if e % 6000 == 0:
#             print("#It is running...",e,"of",l, time.time()-stime,'seconds')
            stime = time.time()
        dim = len(columnLabelOfSimplex[e][1])
        columnInfo = D[e]
        rowlist = columnInfo[0]
        vlist = columnInfo[1]
        if rowlist == [] or max(rowlist) == -1: # check -1 convention.
            lowRindex.append(-1) # -1 is convention.
            continue
        try:
            columnInfoV = V[e]
            rowlistV = columnInfoV[0]
            vlistV = columnInfoV[1]
        except:
            rowlistV = []
            vlistV = {}
        ir = max(rowlist)
        ic = vlist[ir]
        z = True
        while z == True:
            if ir not in lowRindex:
                break
            j = lowRindexInd[ir]
            jr = ir
            jc = lowRvalueDic[jr]
            columnInfoj = D[j]
            rowlistj = columnInfoj[0]
            vlistj = columnInfoj[1]
            #
            try:
                columnInfojV = V[j]
                rowlistjV = columnInfojV[0]
                vlistjV = columnInfojV[1]
            except:
                rowlistjV = []
                vlistjV = {}
            try:
                vlistjV[j]
            except:
                rowlistjV.append(j)
                vlistjV[j] = 1
            c = - ic/jc
            #
            # start R[e] column opertation.
            newrowlist = []
            newvlist = {}
            for r in rowlist:
                if r not in rowlistj:
                    newrowlist.append(r)
                    newvlist[r] = vlist[r]
                else:
                    newv = vlist[r] + c*vlistj[r]
                    if newv != 0:
                        newrowlist.append(r)
                        newvlist[r] = newv
            for rj in rowlistj:
                if rj not in rowlist:
                    newrowlist.append(rj)
                    newvlist[rj] = c*vlistj[rj]
            D[e] = [newrowlist, newvlist]
            # finished computing D[e]
            #
            # start V[e] column opertation.
            newrowlistV = []
            newvlistV = {}
            for rv in rowlistV:
                if rv not in rowlistjV:
                    newrowlistV.append(rv)
                    newvlistV[rv] = vlistV[rv]
                else:
                    newvv = vlistV[rv] + c*vlistjV[rv]
                    if newvv != 0:
                        newrowlistV.append(rv)
                        newvlistV[rv] = newvv
            for rjv in rowlistjV:
                if rjv not in rowlistV:
                    newrowlistV.append(rjv)
                    newvlistV[rjv] = c*vlistjV[rjv]
            V[e] = [newrowlistV, newvlistV]
            rowlistV = newrowlistV
            vlistV = newvlistV
            # finished computing V[e]
            #
            rowlist = newrowlist
            vlist = newvlist
            if rowlist == []:
                ir = -1 # -1 is convention
                ic = 0
                break
            ir = max(rowlist)
            ic = vlist[ir]
        lowRindex.append(ir)
        lowRindexInd[ir] = e
        lowRvalueDic[ir] = ic
        #
        # From now on, printing for finite barcode.
        if D[e][0] == [] or D[e][0] == [-1]:
            births.append(e) ###
            continue
        [rowlista, vlista] = D[e]
        [stepa, columnSimplexa] = columnLabelOfSimplex[e]
        demsionOfColumna = len(columnSimplexa) - 2
        if demsionOfColumna not in listOfDimensionInput:
            continue
        ba = max(rowlista)
        finiteBirths.append(ba) ###
        simplexa = columnLabelOfSimplexList[ba]
        if len(simplexa) == 1:
            if annotate:
                generator = ''
                for ej, boundaryIndex in enumerate(rowlista):
                    sign = int(vlista[boundaryIndex]) * -1
                    if ej == 0:
                        if sign == -1:
                            generator += " - " + str(columnLabelOfSimplexList[boundaryIndex])
                        else:
                            generator += str(columnLabelOfSimplexList[boundaryIndex])
                        continue
                    if sign == -1:
                        generator += " - " + str(columnLabelOfSimplexList[boundaryIndex])
                    elif sign == 1:
                        generator += " + " + str(columnLabelOfSimplexList[boundaryIndex])
                    else:
                        return # return None
                if birthDeathSimplex:
                    oi = [demsionOfColumna,[0, simplexa], columnLabelOfSimplex[e], generator]
                else:
                    oi = [demsionOfColumna,[0, columnLabelOfSimplex[e][0]], generator]
                # if not sortDimension:
                #     print(oi)
                o.append(oi)
            else:
                if birthDeathSimplex:
                    oi = [demsionOfColumna,[0, simplexa], columnLabelOfSimplex[e]]
                else:
                    oi = [demsionOfColumna,[0, columnLabelOfSimplex[e][0]]]
                # if not sortDimension:
                #     print(oi)
                o.append(oi)
            continue
        if stepa != columnLabelOfSimplex[ba][0]:
            if annotate:
                generator = ''
                for ej, boundaryIndex in enumerate(rowlista):
                    sign = int(vlista[boundaryIndex]) * -1
                    if ej == 0:
                        if sign == -1:
                            generator += " - " + str(columnLabelOfSimplexList[boundaryIndex])
                        else:
                            generator += str(columnLabelOfSimplexList[boundaryIndex])
                        continue
                    if sign == -1:
                        generator += " - " + str(columnLabelOfSimplexList[boundaryIndex])
                    elif sign == 1:
                        generator += " + " + str(columnLabelOfSimplexList[boundaryIndex])
                    else:
                        return # return None
                if birthDeathSimplex:
                    oi = [demsionOfColumna,columnLabelOfSimplex[ba], columnLabelOfSimplex[e], generator]
                else:
                    oi = [demsionOfColumna,[columnLabelOfSimplex[ba][0], columnLabelOfSimplex[e][0]], generator]
                # if not sortDimension:
                #     print(oi)
                o.append(oi)
            else:
                if birthDeathSimplex:
                    oi = [demsionOfColumna,columnLabelOfSimplex[ba], columnLabelOfSimplex[e]]
                else:
                    oi = [demsionOfColumna,[columnLabelOfSimplex[ba][0], columnLabelOfSimplex[e][0]]]
                # if not sortDimension:
                #     print(oi)
                o.append(oi)
#     print("FiniteIntervalComputingDoneTotal",time.time()-astime,'seconds')
    #
    stime = time.time()
    Vkeys = V.keys()
    if not onlyFiniteInterval:
        for b in births:
            [step, columnSimplex] = columnLabelOfSimplex[b]
            demsionOfColumn = len(columnSimplex) - 1
            if demsionOfColumn in listOfDimensionInput and b not in finiteBirths:
                if annotate:
                    if b in Vkeys:
                        [rowlist, vlist] = V[b]
                        generator = str(columnSimplex)
                        for e, boundaryIndex in enumerate(rowlist):
                            sign = int(vlist[boundaryIndex])
                            if sign == -1:
                                generator += " - " + str(columnLabelOfSimplexList[boundaryIndex])
                            elif sign == 1:
                                generator += " + " + str(columnLabelOfSimplexList[boundaryIndex])
                            else:
                                return # return None
                    else:
                        generator = str(columnSimplex)
                    if birthDeathSimplex:
                        oi = [demsionOfColumn,[step, columnSimplex], "infty", generator]
                    else:
                        oi = [demsionOfColumn,[step, "infty"], generator]
                    # if not sortDimension:
                    #     print(oi)
                    o.append(oi)
                else:
                    if birthDeathSimplex:
                        oi = [demsionOfColumn,[step, columnSimplex], "infty"]
                    else:
                        oi = [demsionOfColumn,[step, "infty"]]
                    # if not sortDimension:
                    #     print(oi)
                    o.append(oi)
#     print("InfiniteIntervalFinished",time.time()-stime,'seconds')
    # barcodetitleEnd = '-------------------------\n-------------------------\n Barcode End\n-------------------------'
    # if not sortDimension:
        # print(barcodetitleEnd)
    else :
    # if sortDimension :
        # print(barcodetitle)
        oo = []
        oi = list(set([i[0] for i in o]))
        for i in oi:
            for k in o:
                if k[0] == i:
                    # print(k)
                    oo.append(k)
        # print(barcodetitleEnd)
        o = oo
    return o
#
# INPUT: numpy matrix as distance matrix.
def generateBarcode(mat, listOfDimension = [1], numOfDivision = 1000, start = 0, end = 3, exactStep = False, truncate = True, increment = 1e-05, division = True, annotate = True, onlyFiniteInterval = False, checkExistInfty = True, birthDeathSimplex = True, sortDimension = False):
    otime = time.time()
    stepsOfFiltration = generateFiltrationTimes(mat, numOfDivision = numOfDivision, start = start, end = end, exactStep = exactStep, truncate = truncate, increment = increment, division = division)
    if stepsOfFiltration == None:
        return # return None
    #
    l = len(mat)
    listOfDimensionInput = [i for i in listOfDimension]
    # for listing simplex dimensions.
    if onlyFiniteInterval:
        z = [] # z is a list for dimensions of simplices
        for d in listOfDimension:
            z.extend([d, d+1])
        dimensionsOfSimplex = sorted(list(set(z)))
        #
        stime = time.time()
        # for listing 0-simplex by Vietoris-Rips with lexicographic order.
        listOfSimplexWithStep = []
        if 0 in dimensionsOfSimplex:
            listOfSimplexWithStep.append([0, [(i,) for i in range(l)]])
            dimensionsOfSimplexWithout0 = dimensionsOfSimplex[1:]
        else:
            dimensionsOfSimplexWithout0 = dimensionsOfSimplex
    else:
        stime = time.time()
        # for listing 0-simplex by Vietoris-Rips with lexicographic order.
        listOfSimplexWithStep = [[0, [(i,) for i in range(l)]]]
        dimensionsOfSimplex = [i for i in range(max(listOfDimension)+2)]
        listOfDimension = dimensionsOfSimplex[:-1]
        dimensionsOfSimplexWithout0 = dimensionsOfSimplex[1:]
    #
    listOfSimplexWithStep.extend([[step,[]] for step in stepsOfFiltration])
    listOfSimplexWithStepAndConvention = [[-1,[]]] +listOfSimplexWithStep # [-1,[]] is convention.
    for dim in dimensionsOfSimplexWithout0:
        for tup in it.combinations(range(l), dim + 1):
            v = max([mat[i,j] for (i,j) in it.combinations(tup, 2)])
            for e, [step, _] in enumerate(listOfSimplexWithStep):
                if v <= step and v > listOfSimplexWithStepAndConvention[e][0]:
                    [step, listOfSimplex] = listOfSimplexWithStep[e]
                    listOfSimplex.append(tup)
                    listOfSimplexWithStep[e] = [step, listOfSimplex]
                    break
    #
#     print('listOfSimplexWithStep',time.time() - stime,'seconds')
    stime = time.time()
    [boundaryMatrix, columnLabelOfSimplex] = generateBoundaryMatrix(listOfSimplexWithStep, dim =  dimensionsOfSimplex)
#     print('gettingBoundaryMatrixElements',time.time() - stime,'seconds')
    stime = time.time()
    birthDeath = pHcolGenerateRVmatrix(boundaryMatrix, columnLabelOfSimplex, listOfDimensionInput = listOfDimensionInput, annotate = annotate, onlyFiniteInterval = onlyFiniteInterval, birthDeathSimplex = birthDeathSimplex, sortDimension = sortDimension)
#     print('phColOperationTotal',time.time() - stime,'seconds')
#     print('wholeRunningTime',time.time() - otime,'seconds')
    return birthDeath

def plot_OM(overlapped_cycles : pd.DataFrame, songname : str | None = None) :

    overlapped_cycles_transposed = overlapped_cycles.transpose()
    mat1 = overlapped_cycles_transposed.to_numpy()

    # plot overlap matrix
    fig, ax = plt.subplots(1, 1, figsize=(24, 15))

    from matplotlib.colors import ListedColormap

    ax=sns.heatmap(mat1, cmap=ListedColormap(['white', (0.2,0.8,0.8)]),yticklabels = ['C'+str(i+1) for i in range(len(mat1))],cbar=False)
    ax.axhline(y = 0, color='k',linewidth = 1)
    ax.axhline(y = len(mat1)-0.01, color = 'k',
                linewidth = 1)
    ax.axvline(x = 0, color = 'k',
                linewidth = 1)
    ax.axvline(x = len(mat1[0])-0.1,
                color = 'k', linewidth = 1)
    n = 15
    [l.set_visible(False) for (i,l) in enumerate(ax.xaxis.get_ticklabels()) if i % n != 0]

    plt.setp(ax.get_xticklabels(), rotation=360)
    ax.tick_params(axis=u'both', which=u'both',length=0)

    
    if songname is not None : 
        plt.title(songname+'_OM') 
        plt.savefig(songname + '_OM.png', bbox_inches='tight')
    else :
        plt.title('Overlap Matrix') 

    # 중첩행렬을 그려 줍니다. 
    plt.show()


# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------- 250514 ALGORITHM 1 일부 수정 ------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #
# ------------------------------------------------------------------------ #

def get_note_by_label(value, dictionary):
  """notes_label에서 특정 value에 해당하는 key를 찾아 반환합니다.
  해당하는 key가 없으면 None을 반환합니다.
  value가 여러 key에 걸쳐 있다면, 가장 먼저 찾은 key를 반환합니다.
  """
  for key, val in dictionary.items():
    if val == (value+1): # generateBarcode의 분석은 인덱싱을 0부터 하는데 비교할 notes_label 딕셔너리엔 1부터 되어있으므로
      return key

def cycle_generate(ci, notes_label):
    """ 
    notes_label를 얻는 방법 :
      notes_label, notes_counts = notes_label_n_counts(module_notes)
       """
    cyclei = []
    for i in ci:
        midi, tempo = get_note_by_label(i, notes_label)
        cyclei.append([midi,tempo])
    return cyclei

def frequent_nodes(all_cycle_set, keys):
  """
  주어진 키 목록에 해당하는 set들을 all_cycle_set 딕셔너리에서 가져와
  모든 set을 순회한 후, 전체 원소들의 등장 횟수를 계산하고,
  각 원소가 count만큼 들어있는 튜플을 반환합니다.

  Args:
    all_cycle_set: (dict) 키는 set 레이블, 값은 set (집합) 객체인 딕셔너리.
    keys: (list) 순회할 all_cycle_set의 키 목록.

  Returns:
    (tuple) 각 원소가 해당 원소의 등장 횟수만큼 반복되어 들어있는 튜플.
  """

  elt_counts = {}
  for key in keys:
    elts = all_cycle_set[key]
    for elt in elts:
      if elt in elt_counts:
        elt_counts[elt] += 1
      else:
        elt_counts[elt] = 1

  # 각 원소가 count만큼 반복되어 들어있는 튜플 생성
  result_tuple = ()
  for elt, count in elt_counts.items():
    result_tuple += (elt,) * count  # 튜플 덧셈을 사용하여 반복 추가

  return result_tuple

def node_intersect(overlap_matrix, all_cycle_set):

    if np.sum(overlap_matrix) == 0:
        err_message = 'no intersection error ......'
        print(err_message)
        return
    set_number = np.nonzero(overlap_matrix)

    y_tuple = frequent_nodes(all_cycle_set, set_number[0])
    return y_tuple
        
def node_union(overlap_matrix, all_cycle_set):

    if np.sum(overlap_matrix) == 0:
        err_message = 'no intersection error ......'
        print(err_message)
        return
    set_number = np.nonzero(overlap_matrix)
    n_s_n = len(set_number[0])

    for k in range(n_s_n):
        nl = set_number[0][k]
        if k ==0:
            y = all_cycle_set[nl]
        elif k >0:
            y = y.union(all_cycle_set[nl])
    return y

def choose_node_ts(z,notes_label,onset):

    node_current = cycle_generate([z], notes_label)
    int_midi_number= node_current[0][0]
    int_midi_duration= node_current[0][1]
    # dur_hibari = int_midi_duration/2 # 8분음표를 한 박자로 했으므로 duration_in_quarter로 했을 때 0.5가 곱해지도록
    
    n1 = (onset, int_midi_number, onset + int_midi_duration)
    n2 = (int_midi_number, int_midi_duration)

    return n1, n2

def create_instrument_part(instrument_notes, instrument_number, tempo_bpm, start_offset):
    """정제된 음표 리스트를 music21 Stream으로 변환하여 악기별 파트를 생성합니다."""

    # Stream 객체 생성
    p = stream.Part()
    p.id = f"Instrument {instrument_number}"
    p.insert(0, instrument.Instrument(instrumentNumber=instrument_number))  # 악기 정보 설정
    p.insert(0, meter.TimeSignature('4/4'))  # 4/4 박자
    p.insert(0, clef.TrebleClef())

    # 템포 설정 (MetronomeMark 객체 사용)
    mm = tempo.MetronomeMark(number=tempo_bpm)
    p.insert(0, mm)

    # 음표들을 시작 시간을 기준으로 그룹화하여 화음 처리
    notes_by_start_time = {}
    for start_eighth, pitch, end_eighth in instrument_notes:  # notes는 리스트, 각 요소는 튜플
        if start_eighth not in notes_by_start_time:
            notes_by_start_time[start_eighth] = []
        notes_by_start_time[start_eighth].append((pitch, end_eighth))

    # 모든 가능한 시작 시간 생성 (0부터 가장 늦은 end_eighth - 1까지)
    max_end_eighth = max(end_eighth for _, _, end_eighth in instrument_notes)
    all_possible_start_times = list(range(max_end_eighth))
    # print(max_end_eighth)
    # print(all_possible_start_times)

    # 활성화된 음을 추적하기 위한 set
    # active_notes = set()

    # 쉼표와 음표를 Stream에 추가
    for start_eighth in all_possible_start_times:
        # 현재 시간에 활성화된 음이 있는지 확인
        is_active = False
        for start, pitch, end in instrument_notes:
            if start <= start_eighth < end:
                is_active = True
                break

        # 활성화된 음이 없으면 쉼표 추가
        if not is_active:
            # print(f"    Instrument {instrument_number}: Adding rest at start_eighth: {start_eighth}")
            r = note.Rest()
            r.offset = float(start_eighth / 2) + start_offset  # offset 값 명시적 타입 변환
            r.quarterLength = 0.5  # 8분음표 길이
            p.append(r)
        else:
            # 해당 시작 시간에 음표가 있는지 확인
            if start_eighth in notes_by_start_time:
                note_info_list = notes_by_start_time[start_eighth]
                if len(note_info_list) > 1:  # 화음인 경우
                    # 화음 구성 음표들을 생성
                    chord_notes = []
                    for pitch, end_eighth in note_info_list:
                        n = note.Note()  # 노트 객체 먼저 생성
                        n.pitch.midi = pitch  # pitch 값 설정
                        duration_eighth = (end_eighth - start_eighth) / 2
                        # 최소 지속 시간 제한 (1/128분음표)
                        # if duration_eighth < 1/128:
                            # duration_eighth = 1/128
                        n.quarterLength = float(duration_eighth)  # quarterLength 값 명시적 타입 변환
                        chord_notes.append(n)

                    # 화음 생성 및 위치 설정
                    c = chord.Chord(chord_notes)
                    c.offset = float(start_eighth / 2) + start_offset  # offset 값 명시적 타입 변환
                    p.append(c)
                    # print(f"    Instrument {instrument_number}: Adding chord at start_eighth: {start_eighth}")
                else:  # 단일 음표인 경우
                    pitch, end_eighth = note_info_list[0]
                    n = note.Note()  # 노트 객체 먼저 생성
                    n.pitch.midi = pitch  # pitch 값 설정
                    duration_eighth = (end_eighth - start_eighth) / 2
                    # 최소 지속 시간 제한 (1/128분음표)
                    # if duration_eighth < 1/128:
                        # duration_eighth = 1/128
                    n.quarterLength = float(duration_eighth)  # quarterLength 값 명시적 타입 변환
                    n.offset = float(start_eighth / 2) + start_offset  # offset 값 명시적 타입 변환
                    p.append(n)
                    # print(f"    Instrument {instrument_number}: Adding note at start_eighth: {start_eighth}")
            else:
                # 해당 시작 시간에 음표가 없지만 활성화된 음이 있는 경우 (지속되는 음)
                pass  # 아무것도 하지 않음 (이미 이전 음표에 의해 처리됨)

    return p

def notes_to_score_xml_(notes, tempo_bpm=66, file_name="temp_score", output_dir = "./"):
    """정제된 음표 리스트를 music21 Stream으로 변환하고 MusicXML 파일로 저장합니다."""

    # 전체 Stream 객체 생성
    s = stream.Score()

    # 악기별 Stream 객체 생성 및 전체 Stream에 추가
    instrument_streams = []
    for i, instrument_notes in enumerate(notes):  # instruments 개수만큼 반복
        p = create_instrument_part(instrument_notes, i + 1, tempo_bpm, start_offset = notes[0][0][0])
        instrument_streams.append(p)
        s.append(p)

    # MusicXML 파일로 저장
    musicxml_file = os.path.join(output_dir, f'{file_name}.musicxml')    # 디렉토리 경로와 파일 이름을 결합하여 전체 파일 경로 생성

    # 디렉토리가 존재하지 않으면 생성
    os.makedirs(output_dir, exist_ok=True)  # exist_ok=True: 이미 존재하면 에러 발생 X

    s.write('musicxml', fp=musicxml_file)
    print(f"MusicXML 파일이 저장되었습니다: {musicxml_file}")

    return s

def algorithm1(node_pool, inst_len : list[int], notes_label, overlap_matrix, all_cycle_set) :

    s1 = [] 

    resampled = 0
    length = len(inst_len)

    onset_checker = dict()
    for i in range(length) :
        onset_checker[i] = []

    node_pool_t = tuple(node_pool)

    for num_nodes_in_a_chord in range(inst_len[0]) :

        while True: 
            z = random.choice(node_pool_t) 
            n1, n2 = choose_node_ts(z,notes_label,0)

            if n2 not in onset_checker[0]: #새로 뽑힌 n2이 onset_checker[0]에 없을 때
                break  

        for i in range(0+1, n1[2]):
            inst_len[i] -= 1 # n1이 활성화된 구간(i 시점들)에서 활성화될 수 있는 음의 갯수를 하나 빼주기    
            onset_checker[i].append(n2)
        s1.append(n1)
        onset_checker[0].append(n2)

    for j in range (1,length-1):

        # print(f"random sampling for {j}th time...")
        
        for num_nodes_in_a_chord in range(inst_len[j]) :

            flag_current = sum(overlap_matrix[j,:]) #int(np.sum(overlap_matrix[j,:]))
            flag_next = sum(overlap_matrix[j+1,:]) #int(np.sum(overlap_matrix[j+1,:]))
            flag_previous = sum(overlap_matrix[j-1,:]) #int(np.sum(overlap_matrix[j-1,:]))

            if flag_current == 0:

                while True: 

                    if flag_previous >0 and flag_next > 0:
                        y_previous = node_union(overlap_matrix[j-1,:], all_cycle_set)
                        y_next = node_union(overlap_matrix[j+1,:], all_cycle_set)
                        y = y_previous.union(y_next)
                        z = random.choice(node_pool_t) #int(random.choice(node_pool_t))
                        while z in y:
                            z = random.choice(node_pool_t) #int(random.choice(node_pool_t))

                    elif flag_previous >0 and flag_next ==0 :
                        y = node_union(overlap_matrix[j-1,:], all_cycle_set)
                        z = random.choice(node_pool_t) #int(random.choice(node_pool_t))
                        while z in y:
                            z = random.choice(node_pool_t) #int(random.choice(node_pool_t))

                    elif flag_previous == 0 and flag_next > 0:
                        y = node_union(overlap_matrix[j+1,:], all_cycle_set)
                        z = random.choice(node_pool_t) #int(random.choice(node_pool_t))
                        while z in y:
                            z = random.choice(node_pool_t) #int(random.choice(node_pool_t))


                    elif flag_previous == 0 and flag_next == 0:
                        z = random.choice(node_pool_t) #int(random.choice(node_pool_t))
                    
                    print(f"{j}th z is {z}, beep--")
                    n1, n2 = choose_node_ts(z,notes_label,j)
                    if (n1[2] >= length) or (n2 in onset_checker[j]):  
                        resampled += 1
                        print(f"outta time or sampled already. Resampling nodes for {j}")
                        continue  # z = random.choice(y)부터 다시
                    
                    s1.append(n1)
                    onset_checker[j].append(n2)
                    for i in range(j+1, n1[2]):
                        inst_len[i] -= 1
                        onset_checker[i].append(n2)
                    break

                #########
                # newnode = nodelist[z]
                # Lnew.append(newnode)
                #########

            else:
                y = node_intersect(overlap_matrix[j,:], all_cycle_set)
                # print(y, j)
                while True: 
                    z = random.choice(y) #int(random.choice(y))
                    print(f"{j}th z is {z}")
                    n1, n2 = choose_node_ts(z,notes_label,j)
                    if (n2 in onset_checker[j]) :  # or (n1[2] >= length)  
                        resampled += 1
                        print(f"{n2} got sampled again")
                        print(f"Sampled already. Resampling nodes for {j}")
                        # print(f"outta time or sampled already. Resampling nodes for {j}")
                        continue  # z = random.choice(y)부터 다시

                    # 정상적인 경우에만 다음 코드 실행
                    s1.append(n1)
                    onset_checker[j].append(n2)
                    for i in range(j+1, min(n1[2], length)):
                        inst_len[i] -= 1
                        onset_checker[i].append(n2)
                    break

                #########
                # newnode = nodelist[z]
                # Lnew.append(newnode)
                #########

    if not (inst_len[-1] <= 0) : 
        for num_nodes_in_a_chord in range(inst_len[-1]) :
            while True :
                print("came here4")
                z = random.choice(node_pool_t) # int(random.choice(node_pool_t))
                # n1 = choose_node(z,nodelist,pitchlist,midilist)
                n1, n2 = choose_node_ts(z,notes_label,length-1)
                if n2 in onset_checker[length-1] :
                    continue

                print(f"last z is {z}")
                s1.append(n1)
                break
    else :
        print("there is no room for ")

    #########
    # newnode = nodelist[z]
    # Lnew.append(newnode)
    #########

    stream = notes_to_score_xml_([s1], file_name=f"{get_now()}", output_dir = "./test_xml")
    print(f"총 {resampled}번 재추출이 있었습니다.")

    return s1
    # fp=s1.write('midi',fp=path+"output_from"+songname+"_"+str(get_now())+".midi")
    # fp2=s1.write('musicxml.pdf',path+"output_from"+songname+"_"+str(get_now())+".pdf")
