"""
BMI指数计算
^^^^^^^^^^^

计算 `BMI指数 <https://en.wikipedia.org/wiki/Body_mass_index>`_ 的简单应用

:demo_host:`Demo地址 </?pywebio_api=bmi>`  `源码 <https://github.com/wang0618/PyWebIO/blob/dev/demos/bmi.py>`_
"""
from pywebio import start_server
from pywebio.input import *
from pywebio.output import *
from pywebio.session import set_env


def main():
    """BMI Calculation

    计算BMI指数的简单应用
    """

    put_markdown("""# BMI指数

    [`BMI指数`](https://baike.baidu.com/item/%E4%BD%93%E8%B4%A8%E6%8C%87%E6%95%B0/1455733)（Body Mass Index，BMI），是用体重千克数除以身高米数的平方得出的数字，是国际上常用的衡量人体胖瘦程度以及是否健康的一个标准。
    
    成年人的BMI值处于以下阶段
    
    | 体形分类 | BMI值范围 |
    | -------- | --------- |
    | 极瘦   | BMI<14.9    |
    | 偏瘦    | 14.9≤BMI<18.4     |
    | 正常    | 18.4≤BMI<22.9     |
    | 过重    |  22.9≤BMI<27.5  |
    | 肥胖    |  27.5≤BMI<40  |
    | 非常肥胖 |     BMI≥40      |
    
    ## BMI指数计算器
    本程序的源代码[链接](https://github.com/wang0618/PyWebIO/blob/dev/demos/bmi.py)
    
    """, strip_indent=4)

    info = input_group('计算BMI：', [
        input("请输入你的身高(cm)", name="height", type=FLOAT),
        input("请输入你的体重(kg)", name="weight", type=FLOAT),
    ])

    BMI = info['weight'] / (info['height'] / 100) ** 2

    top_status = [(14.9, '极瘦'), (18.4, '偏瘦'),
                  (22.9, '正常'), (27.5, '过重'),
                  (40.0, '肥胖'), (float('inf'), '非常肥胖')]

    for top, status in top_status:
        if BMI <= top:
            put_markdown('你的 BMI 值: `%.1f`，身体状态：`%s`' % (BMI, status))
            break


if __name__ == '__main__':
    start_server(main, debug=True, port=8080, cdn=False)
