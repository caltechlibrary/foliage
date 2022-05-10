"""
输出演示
^^^^^^^^^^^
演示PyWebIO支持的各种输出形式

:demo_host:`Demo地址 </?pywebio_api=output_usage>`  `源码 <https://github.com/wang0618/PyWebIO/blob/dev/demos/output_usage.py>`_
"""
from pywebio import start_server
from pywebio.output import *
from pywebio.session import hold, set_env
from functools import partial


def code_block(code, strip_indent=4):
    if strip_indent:
        lines = (
            i[strip_indent:] if (i[:strip_indent] == ' ' * strip_indent) else i
            for i in code.splitlines()
        )
        code = '\n'.join(lines)
    code = code.strip('\n')

    def run_code(code, scope):
        with use_scope(scope):
            exec(code, globals())

    with use_scope() as scope:
        put_code(code, 'python')
        put_buttons([{'label': '运行', 'value': '', 'color': 'success'}],
                    onclick=[partial(run_code, code=code, scope=scope)], small=True)


async def main():
    """PyWebIO输出演示

    演示PyWebIO支持的各种输出形式
    """
    put_markdown("""# PyWebIO 输出演示
    
    在[这里](https://github.com/wang0618/PyWebIO/blob/dev/demos/output_usage.py)可以获取本Demo的源码。
    
    本Demo仅提供了PyWebIO输出模块的部分功能的演示，完整特性请参阅[用户指南](https://pywebio.readthedocs.io/zh_CN/latest/guide.html)。
    
    PyWebIO的输出函数都定义在 `pywebio.output` 模块中，可以使用 `from pywebio.output import *` 引入。

    ### 基本输出
    PyWebIO提供了一些便捷函数来输出表格、链接等格式:
    """, strip_indent=4)

    code_block(r"""
    # 文本输出
    put_text("Hello world!")

    # 表格输出
    put_table([
        ['商品', '价格'],
        ['苹果', '5.5'],
        ['香蕉', '7'],
    ])

    # Markdown输出
    put_markdown('~~删除线~~')

    # 文件输出
    put_file('hello_word.txt', b'hello word!')
    """)

    put_markdown(r"""PyWebIO提供的全部输出函数请参考PyWebIO文档
    
    ### 组合输出
    
    函数名以 `put_` 开始的输出函数，可以与一些输出函数组合使用，作为最终输出的一部分。

    比如`put_table()`支持以`put_xxx()`调用作为单元格内容:
    """, strip_indent=4)

    code_block(r"""
    put_table([
        ['Type', 'Content'],
        ['html', put_html('X<sup>2</sup>')],
        ['text', '<hr/>'],  # 等价于 ['text', put_text('<hr/>')]
        ['buttons', put_buttons(['A', 'B'], onclick=toast)],  
        ['markdown', put_markdown('`Awesome PyWebIO!`')],
        ['file', put_file('hello.text', b'hello world')],
        ['table', put_table([['A', 'B'], ['C', 'D']])]
    ])
    """)

    put_markdown(r"""类似地，`popup()`也可以将`put_xxx()`调用作为弹窗内容:
    
    """, strip_indent=4)

    code_block(r"""
    popup('Popup title', [
        put_html('<h3>Popup Content</h3>'),
        'plain html: <br/>',  # 等价于 put_text('plain html: <br/>')
        put_table([['A', 'B'], ['C', 'D']]),
        put_buttons(['close_popup()'], onclick=lambda _: close_popup())
    ])
    """)

    put_markdown(r"更多接受`put_xxx()`作为参数的输出函数请参考函数文档。")

    put_markdown(r"""### 事件回调
    PyWebIO允许你输出一些控件，当控件被点击时执行提供的回调函数，就像编写GUI程序一样。
    
    下面是一个例子:
    ```python
    from functools import partial

    def edit_row(choice, row):
        put_markdown("> You click`%s` button ar row `%s`" % (choice, row))

    put_table([
        ['Idx', 'Actions'],
        [1, put_buttons(['edit', 'delete'], onclick=partial(edit_row, row=1))],
        [2, put_buttons(['edit', 'delete'], onclick=partial(edit_row, row=2))],
        [3, put_buttons(['edit', 'delete'], onclick=partial(edit_row, row=3))],
    ])
    ```
    `put_table()`的调用不会阻塞。当用户点击了某行中的按钮时，PyWebIO会自动调用相应的回调函数:
    
    """, strip_indent=4)

    from functools import partial

    @use_scope('table-callback')
    def edit_row(choice, row):
        put_markdown("> You click `%s` button ar row `%s`" % (choice, row))

    put_table([
        ['Idx', 'Actions'],
        [1, put_buttons(['edit', 'delete'], onclick=partial(edit_row, row=1))],
        [2, put_buttons(['edit', 'delete'], onclick=partial(edit_row, row=2))],
        [3, put_buttons(['edit', 'delete'], onclick=partial(edit_row, row=3))],
    ])
    set_scope('table-callback')

    put_markdown(r"""当然，PyWebIO还支持单独的按钮控件:
    ```python
    def btn_click(btn_val):
        put_markdown("> You click `%s` button" % btn_val)

    put_buttons(['A', 'B', 'C'], onclick=btn_click)
    ```
    """, strip_indent=4)

    @use_scope('button-callback')
    def btn_click(btn_val):
        put_markdown("> You click `%s` button" % btn_val)

    put_buttons(['A', 'B', 'C'], onclick=btn_click)
    set_scope('button-callback')

    put_markdown(r"""### 输出域Scope

    PyWebIO使用Scope模型来对内容输出的位置进行灵活地控制，PyWebIO的内容输出区可以划分出不同的输出域，PyWebIO将输出域称作`Scope`。
    
    输出域为输出内容的容器，各个输出域之间上下排列，输出域也可以进行嵌套。
    
    每个输出函数（函数名形如 `put_xxx()` ）都会将内容输出到一个Scope，默认为”当前Scope”，”当前Scope”由运行时上下文确定，输出函数也可以手动指定输出到的Scope。Scope名在会话内唯一。
    
    可以使用 `use_scope()` 开启并进入一个新的输出域，或进入一个已经存在的输出域:

    ```python
    with use_scope('A'):
        put_text('Text in scope A')
    
        with use_scope('B'):
            put_text('Text in scope B')
    
    with use_scope('C'):
        put_text('Text in scope C')
    ```
    以上代码将会产生如下Scope布局:
    """, strip_indent=4)
    with use_scope('A'):
        put_text('Text in scope A')

        with use_scope('B'):
            put_text('Text in scope B')

    with use_scope('C'):
        put_text('Text in scope C')

    put_html("""<style>                                           
    #pywebio-scope-A {border: 1px solid red;}                    
    #pywebio-scope-B {border: 1px solid blue;margin:2px}         
    #pywebio-scope-C {border: 1px solid green;margin-top:2px}    
    </style><br/>""")

    put_markdown(r"""
    输出函数（函数名形如 `put_xxx()` ）在默认情况下，会将内容输出到”当前Scope”，可以通过 `use_scope()` 设置运行时上下文的”当前Scope”。
    
    此外，也可以通过输出函数的 scope 参数指定输出的目的Scope:
    """, strip_indent=4)

    put_grid([
        [put_code("put_text('A', scope='A')", 'python'), None, put_buttons(['运行'], [lambda: put_text('A', scope='A')])],
        [put_code("put_text('B', scope='B')", 'python'), None, put_buttons(['运行'], [lambda: put_text('B', scope='B')])],
        [put_code("put_text('C', scope='C')", 'python'), None, put_buttons(['运行'], [lambda: put_text('C', scope='C')])],
    ], cell_widths='1fr 10px auto')

    put_markdown(r"""输出函数可以使用position参数指定内容在Scope中输出的位置
    ```python
    put_text(now(), scope='A', position=...)
    ```
    """, strip_indent=4)
    import datetime

    put_buttons([('position=%s' % i, i) for i in [1, 2, 3, -1, -2, -3]],
                lambda i: put_text(datetime.datetime.now(), position=i, scope='A'), small=True)

    put_markdown(r"除了 `use_scope()` , PyWebIO同样提供了以下scope控制函数： ")

    put_grid([
        [put_code("clear('B')  # 清除Scope B中的内容", 'python'), None, put_buttons(['运行'], [lambda: clear('B')])],
        [put_code("remove('C')  # 移除Scope C", 'python'), None, put_buttons(['运行'], [lambda: remove('C')])],
        [put_code("scroll_to('A')  # 将页面滚动到Scope A处", 'python'), None, put_buttons(['运行'], [lambda: scroll_to('A')])],
    ], cell_widths='1fr 10px auto')

    put_markdown(r"""### 布局
    一般情况下，使用上文介绍的各种输出函数足以完成各种内容的展示，但直接调用输出函数产生的输出之间都是竖直排列的，如果想实现更复杂的布局（比如在页 面左侧显示一个代码块，在右侧显示一个图像），就需要借助布局函数。

    `pywebio.output` 模块提供了3个布局函数，通过对他们进行组合可以完成各种复杂的布局:
    
     - `put_row()` : 使用行布局输出内容. 内容在水平方向上排列
     - `put_column()` : 使用列布局输出内容. 内容在竖直方向上排列
     - `put_grid()` : 使用网格布局输出内容

    比如，通过通过组合 `put_row()` 和 `put_column()` 实现的布局:
    """, strip_indent=4)

    code_block(r"""
    put_row([
        put_column([
            put_code('A'),
            put_row([
                put_code('B1'), None,  # None 表示输出之间的空白
                put_code('B2'), None,
                put_code('B3'),
            ]),
            put_code('C'),
        ]), None,
        put_code('D'), None,
        put_code('E')
    ])
    """)

    put_markdown(r"""
    ### 样式
    
    如果你熟悉 CSS样式 ，你还可以使用 `style()` 函数给输出设定自定义样式。

    可以给单个的 `put_xxx()` 输出设定CSS样式，也可以配合组合输出使用:
    """, strip_indent=4)

    code_block(r"""
    style(put_text('Red'), 'color: red')
    
    put_table([
        ['A', 'B'],
        ['C', style(put_text('Red'), 'color: red')],
    ])
    """, strip_indent=4)

    put_markdown(r"`style()` 也接受列表作为输入:")

    code_block(r"""
    style([
        put_text('Red'),
        put_markdown('~~del~~')
    ], 'color: red')
    
    put_collapse('title', style([
        put_text('text'),
        put_markdown('~~del~~'),
    ], 'margin-left: 20px'))

    """, strip_indent=4)

    put_markdown("""----
    PyWebIO的输出演示到这里就结束了，更多内容请访问PyWebIO[用户指南](https://pywebio.readthedocs.io/zh_CN/latest/guide.html)和[output模块文档](https://pywebio.readthedocs.io/zh_CN/latest/output.html)。
    """, lstrip=True)

    await hold()


if __name__ == '__main__':
    start_server(main, debug=True, port=8080, cdn=False)
