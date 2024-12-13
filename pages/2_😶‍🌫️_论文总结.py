from utils import extract_files, is_token_expired, get_content_by_uid, file_summary, save_content_to_database, text_extraction


import json
import streamlit as st


st.title('😶‍🌫️论文总结')


def main():
    if not st.session_state.files:
        st.write('### 还没上传文档哦')
    else:
        tabs = st.tabs([item['file_name']
                        for item in st.session_state.files])
        for index, item in enumerate(st.session_state.files):
            with tabs[index]:
                st.write('## ' + item['file_name'] + '\n')
                content = get_content_by_uid(item['uid'], 'file_summary')
                if content is not None:
                    file_summary(content) 
                else:
                    with st.spinner('解析文档中 ...'):
                        result = file_summary(item['file_path'])
                        if not result:
                            st.write('### 大模型貌似开小差了～重新试试吧！\n')
                        else:
                            # 保存到数据库
                            save_content_to_database(uid=st.session_state['files'][index]['uid'],
                                                 file_path=st.session_state['files'][index]['file_path'],
                                                 content=result,
                                                 content_type='file_summary')



if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
else:
    main()
