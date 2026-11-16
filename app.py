import json
import sqlite3
import pandas as pd
import streamlit as st

def init_db():
    conn = sqlite3.connect("results.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            class_name TEXT, student TEXT, task_id TEXT, skill TEXT, score INTEGER, phase TEXT, module TEXT
        )
    """)
    return conn

with open("tasks.json", "r", encoding="utf-8") as f:
    TASKS = json.load(f)

conn = init_db()
st.set_page_config(page_title="English 5 Diagnostic", layout="centered")
st.title("English 5: Diagnostic & Feedback")

menu = st.sidebar.radio("Режим", ["Ученик", "Учитель"])

if menu == "Ученик":
    st.subheader("Вход для ученика")
    class_name = st.selectbox("Выбери свой класс:", ["5А", "5Б", "5В", "5Г", "5Д", "Другой"])
    student = st.text_input("Введи свой код (например, S01)")
    
    modules = sorted(list(set([t["module"] for t in TASKS])))
    selected_module = st.selectbox("Выбери модуль:", modules)
    phase = st.selectbox("Этап теста", ["pre", "post"])
    
    module_tasks = [t for t in TASKS if t["module"] == selected_module]
    
    if student:
        if st.button("Начать тест"):
            st.session_state.started = True
            st.session_state.current_module = selected_module

        if st.session_state.get("started") and st.session_state.get("current_module") == selected_module:
            for task in module_tasks:
                st.markdown(f"**{task['prompt']}**")
                choice = st.radio("Выбери ответ:", task["options"], key=task["id"])
                
                if st.button("Ответить", key="btn_" + task["id"]):
                    score = 1 if choice == task["answer"] else 0
                    conn.execute(
                        "INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (class_name, student, task["id"], task["skill"], score, phase, selected_module)
                    )
                    conn.commit()
                    st.success("Сохранено!")
            
            # ИСПРАВЛЕННАЯ СТРОКА ЗДЕСЬ:
            query = "SELECT * FROM results WHERE class_name=? AND student=? AND phase=? AND module=?"
            student_data = pd.read_sql_query(query, conn, params=(class_name, student, phase, selected_module))
            
            if len(student_data) == len(module_tasks):
                st.success(f"Тест по модулю '{selected_module}' завершён.")
                st.subheader("Твои результаты и рекомендации:")
                
                for skill in ["R1", "R2", "G1", "V1"]:
                    skill_data = student_data[student_data['skill'] == skill]
                    if not skill_data.empty:
                        correct = skill_data['score'].sum()
                        total = len(skill_data)
                        percent = (correct / total) * 100
                        
                        names = {"R1": "Понимание главной мысли", "R2": "Понимание деталей", "G1": "Грамматика", "V1": "Лексика"}
                        
                        if percent >= 80:
                            st.write(f"🟢 **{names[skill]}**: Отличный результат! Ты хорошо справляешься с этим типом заданий.")
                        elif percent >= 50:
                            st.write(f"🟡 **{names[skill]}**: Есть небольшие трудности. Рекомендую посетить консультацию для закрепления материала.")
                        else:
                            st.write(f"🔴 **{names[skill]}**: Пока сложно. Приходи на консультацию в удобное время, мы обязательно разберем эту тему.")

elif menu == "Учитель":
    df = pd.read_sql_query("SELECT * FROM results", conn)
    if df.empty:
        st.info("Данных пока нет.")
    else:
        st.subheader("Результаты по классам")
        
        classes_db = df['class_name'].unique()
        sel_class = st.selectbox("Выбери класс для просмотра:", classes_db)
        
        modules_db = df[df['class_name'] == sel_class]['module'].unique()
        sel_mod = st.selectbox("Посмотреть модуль:", modules_db)
        
        df_mod = df[(df['class_name'] == sel_class) & (df['module'] == sel_mod)]
        
        agg = df_mod.groupby(["phase", "skill"]).agg(
            score=("score", "sum"),
            max_score=("score", "count") 
        ).reset_index()
        agg["percent"] = (agg["score"] / agg["max_score"] * 100).round(1)
        st.bar_chart(agg, x="skill", y="percent", color="phase")
        
        st.subheader(f"Успеваемость учеников {sel_class} (в % верных ответов)")
        pivot_df = df_mod.groupby(['student', 'skill'])['score'].mean().unstack() * 100
        pivot_df = pivot_df.round(1).fillna(0)
        pivot_df = pivot_df.rename(columns={'R1': 'Главная мысль', 'R2': 'Детали', 'G1': 'Грамматика', 'V1': 'Лексика'})
        st.dataframe(pivot_df)
