import json
import logging
import streamlit as st
from utils import get_content_by_uid, text_extraction, \
    save_content_to_database, print_contents, is_token_expired


def main():
    tabs = st.tabs([item['file_name']
                    for item in st.session_state.files])
    for index, item in enumerate(st.session_state.files):
        with tabs[index]:
            st.write('## ' + item['file_name'] + '\n')
            content = get_content_by_uid(item['uid'], 'file_extraction')
            if content is not None:
                print_contents(json.loads(content))
            else:
                with st.spinner('解析文档中 ...'):
                    result, content = text_extraction(item['file_path'])
                    if not result:
                        st.write('### System Wrong!\n')
                    else:
                        print_contents(content)
                        # 保存到数据库
                        save_content_to_database(uid=st.session_state['files'][index]['uid'],
                                                 file_path=st.session_state['files'][index]['file_path'],
                                                 content=json.dumps(content),
                                                 content_type='file_extraction')


st.title('🤓原文提取')
if (not st.session_state['token']) or is_token_expired(st.session_state['token']):
    st.error('还没登录哦')
elif not st.session_state.files:
    st.write('### 还没上传文档哦')
else:
    main()
