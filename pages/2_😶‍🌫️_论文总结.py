import streamlit as st

from utils import is_token_expired

st.title('😶‍🌫️论文总结')


def main():
    if not st.session_state.files:
        st.write('### 还没上传文档哦')
    else:
        pass


if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
else:
    main()
