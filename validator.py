import numpy as np
O_MIN = 100
O_MAX = 10000
P_MIN = 1
P_MAX = 100
S_MIN = 1
S_MAX = 605
Q_MIN = 1
Q_MAX = 60


def order_checker(np_arr):
    for i in range(len(np_arr)):
        o_num = np_arr[i][0]
        pl_num = np_arr[i][1]
        quant = np_arr[i][2]
        sku = np_arr[i][3]
        if c_o_num(o_num) and c_pl(pl_num) and c_sku(sku) and c_quant(quant):
            continue
        else:
            print(f"REVISAR LA ORDEN {o_num}, HAY UN ERROR EN LA LÍNEA {str(i+1)} DEL ARCHIVO DE ÓRDENES")
            print()
            return False
    return True


def c_o_num(o_num):
    if (not np.isnan(o_num)) and O_MIN <= o_num <= O_MAX:
        return True
    else:
        print(f"ERROR EN EL NÚMERO DE ORDEN (FALTA EL NÚMERO DE ORDEN O ESTÁ FUERA DE RANGO)")
        return False


def c_pl(pl_num):
    if (not np.isnan(pl_num)) and P_MIN <= pl_num <= P_MAX:
        return True
    else:
        print(f"ERROR EN LISTA DE PRECIOS {pl_num} (FALTA EL NÚMERO DE LISTA O ESTÁ FUERA DE RANGO)")
        return False


def c_sku(sku):
    if (not np.isnan(sku)) and S_MIN <= sku <= S_MAX:
        return True
    else:
        print(f"ERROR EN EL CÓDIGO DE PRODUCTO (EL SKU {sku}) NO EXISTE")
        return False


def c_quant(quant):
    if (not np.isnan(quant)) and Q_MIN <= quant <= Q_MAX:
        return True
    else:
        print(f"ERROR EN LA CANTIDAD DE PRODUCTOS (LA CANTIDAD {quant} ES MENOR A {Q_MIN} O MAYOR A {Q_MAX})")
        return False