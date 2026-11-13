--
-- PostgreSQL database dump
--

\restrict tCFAnIbcSY9oF57tBi57YDSLIU63G1nEi7y7Lywqwk4WmhInvBUzbHIEIciTuNw

-- Dumped from database version 17.12
-- Dumped by pg_dump version 17.12

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: exercises; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.exercises (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    muscle_group character varying(30) NOT NULL,
    equipment character varying(100),
    technique_tips character varying(500) NOT NULL,
    common_mistakes character varying(500),
    safe_for_lower_back boolean,
    safe_for_knees boolean,
    safe_for_elbows boolean,
    sub_group character varying(50),
    image_url character varying(500),
    image_secondary_url character varying(500),
    video_url character varying(500)
);


ALTER TABLE public.exercises OWNER TO postgres;

--
-- Name: exercises_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.exercises_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.exercises_id_seq OWNER TO postgres;

--
-- Name: exercises_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.exercises_id_seq OWNED BY public.exercises.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    created_at timestamp without time zone,
    full_name character varying(100),
    gender character varying(10),
    age integer,
    height_cm double precision,
    weight_kg double precision,
    goal character varying(30),
    work_schedule character varying(20),
    injury_notes character varying(255),
    is_onboarded boolean
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: workouts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.workouts (
    id integer NOT NULL,
    user_id integer NOT NULL,
    exercise_name character varying(100) NOT NULL,
    sets integer NOT NULL,
    reps integer NOT NULL,
    weight double precision,
    created_at timestamp without time zone
);


ALTER TABLE public.workouts OWNER TO postgres;

--
-- Name: workouts_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.workouts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.workouts_id_seq OWNER TO postgres;

--
-- Name: workouts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.workouts_id_seq OWNED BY public.workouts.id;


--
-- Name: exercises id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exercises ALTER COLUMN id SET DEFAULT nextval('public.exercises_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: workouts id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workouts ALTER COLUMN id SET DEFAULT nextval('public.workouts_id_seq'::regclass);


--
-- Data for Name: exercises; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.exercises (id, name, muscle_group, equipment, technique_tips, common_mistakes, safe_for_lower_back, safe_for_knees, safe_for_elbows, sub_group, image_url, image_secondary_url, video_url) FROM stdin;
1	Гоблет-приседания с гантелью (Goblet Squat)	legs	Гантель	Держи гантель у груди, локти направлены вниз. Садись между пяток с ровной спиной, пятки не отрывай.	Завал корпуса вперёд, сведение коленей внутрь, отрыв пяток от пола.	t	t	t	\N	\N	\N	\N
2	Жим гантелей на наклонной скамье (30°)	chest	Гантели + скамья	Сведи лопатки, прижми таз к скамье. Опускай гантели до лёгкого растяжения грудных, локти под 45° к корпусу.	Разведение локтей под 90° (перегружает плечи), сильный прогиб в пояснице.	t	t	t	\N	\N	\N	\N
3	Тяга гантели одной рукой в упоре о скамью	back	Гантель + скамья	Спина параллельна полу, поясница зафиксирована. Тяни гантель к поясу за счёт отведения локтя назад, не скручивая корпус.	Тяга бицепсом к груди вместо широчайшей, округление поясницы.	t	t	t	\N	\N	\N	\N
4	Махи гантелями в стороны (средняя дельта)	shoulders	Гантели	Лёгкий наклон корпуса вперёд, локти слегка согнуты и смотрят в стороны-назад. Поднимай до уровня плеч без рывка.	Подъём трапециями, задирание кистей выше локтей, читинг поясницей.	t	t	t	\N	\N	\N	\N
5	Румынская тяга с гантелями (RDL)	legs	Гантели	Колени чуть согнуты и зафиксированы. Отводи таз назад с идеально прямой спиной до растяжения бицепса бедра.	Округление поясницы в нижней точке, опускание гантелей слишком низко за счёт спины.	f	t	t	\N	\N	\N	\N
6	Скручивания на полу с контролем поясницы	core	Собственный вес	Поясница плотно прижата к полу. Скручивай грудной отдел к тазу на выдохе без рывков шеей.	Тяга головы руками, отрыв поясницы от пола.	t	t	t	\N	\N	\N	\N
7	Французский жим с гантелями лёжа (нейтральный хват)	arms	Гантели + скамья	Локти зафиксированы и смотрят вверх, ладони друг к другу. Опускай гантели по бокам головы плавно без отбива.	Разъезжание локтей в стороны, слишком большой вес (удар по локтевым связкам).	t	t	f	\N	\N	\N	\N
9	Поочерёдные махи в наклоне с опорой от стены	shoulders	Гантели	Упритесь рукой в стену, выполняйте подконтрольные махи рабочей рукой для изоляции дельт.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	delts	\N	\N	\N
10	Жим гантелей сидя на наклонной скамье (60–75°)	shoulders	Гантели	Спинка 60–75°, поясница прижата. Жмите гантели вверх по дуге без стука наверху.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	delts	\N	\N	\N
11	Махи гантелями в наклоне на заднюю дельту	shoulders	Гантели	Наклон корпуса с ровной спиной, разводите гантели за счёт задних дельт.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	delts	\N	\N	\N
12	Протяжка штанги до центра груди	shoulders	Штанга	Хват на ширине плеч. Плавно тяните гриф строго до центра груди, локти выше кистей.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	delts	\N	\N	\N
13	Шраги с гантелями стоя	back	Гантели	Поднимайте плечи строго вертикально вверх к ушам без вращения, пауза 1 сек.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	traps	\N	\N	\N
14	Шраги со штангой перед собой	back	Штанга	Хват на ширине плеч. Поднимайте плечи вверх за счёт трапеций без раскачки.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	traps	\N	\N	\N
15	Подтягивания на перекладине	back	Турник	Начинайте с опускания и сведения лопаток, тянитесь грудью к перекладине.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	lats	\N	\N	\N
16	Тяга гантели одной рукой в наклоне	back	Гантели	Спина параллельна полу. Тяните гантель к поясу, прижимая локоть к корпусу.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	lats	\N	\N	\N
17	Тяга штанги в наклоне к поясу	back	Штанга	Наклон 45°, поясница в нейтральном прогибе. Тяните гриф к низу живота.	Избегайте рывков, инерции и перегруза суставов.	f	t	t	middle_back	\N	\N	\N
18	Жим гантелей лёжа на наклонной скамье (30°)	chest	Гантели	Лопатки сведены, стопы в пол. Опускайте гантели под углом 45° к корпусу.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	pectorals	\N	\N	\N
19	Жим штанги лёжа на горизонтальной скамье	chest	Штанга	Мост в грудном отделе, лопатки сведены. Опускайте гриф на низ груди.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	pectorals	\N	\N	\N
20	Отжимания на брусьях с акцентом на грудь	chest	Брусья	Лёгкий наклон корпуса вперёд, локти слегка в стороны, без провала в плечах.	Избегайте рывков, инерции и перегруза суставов.	t	t	f	pectorals	\N	\N	\N
21	Сведения рук с гантелями или резинкой	chest	Гантели / Резинка	Локти в мягком сгибе. Сводите руки перед грудью с прожимом в пиковой точке.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	pectorals	\N	\N	\N
22	Гоблет-приседания с гантелью у груди	legs	Гантели	Спина прямая, садитесь между бёдер, колени строго по направлению носков.	Избегайте рывков, инерции и перегруза суставов.	t	f	t	quadriceps	\N	\N	\N
23	Болгарские выпады с гантелями	legs	Гантели	Задняя нога на скамье, опускайтесь вниз с упором в пятку передней ноги.	Избегайте рывков, инерции и перегруза суставов.	t	f	t	quadriceps	\N	\N	\N
24	Румынская тяга с гантелями или штангой	legs	Гантели / Штанга	Колени мягкие, спина прямая. Отводите таз назад до растяжения бицепса бедра.	Избегайте рывков, инерции и перегруза суставов.	f	t	t	hamstrings	\N	\N	\N
25	Ягодичный мост со штангой или гантелью	legs	Штанга / Гантели	Лопатки на скамье, выталкивайте таз вверх без переразгибания поясницы.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	glutes	\N	\N	\N
26	Подъёмы на носки стоя	legs	Гантели / Свой вес	Опускайте пятки вниз до растяжения икроножных, затем высоко на носки.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	calves	\N	\N	\N
27	Подъёмы на носки сидя	legs	Гантели	Вес на нижней части бёдер. Поднимайте пятки вверх в полной амплитуде.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	calves	\N	\N	\N
28	Подъём штанги или EZ-грифа на бицепс стоя	arms	Штанга / EZ-гриф	Локти прижаты по бокам. Поднимайте гриф без раскачки спиной.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	biceps	\N	\N	\N
29	Сгибания с гантелями с супинацией	arms	Гантели	Разворачивайте кисть мизинцем вверх для пикового сокращения бицепса.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	biceps	\N	\N	\N
30	Сгибания рук «Молотки» с гантелями	arms	Гантели	Нейтральный хват ладонями друг к другу для проработки брахиалиса.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	biceps	\N	\N	\N
31	Разгибания рук с резинкой или на блоке	arms	Резинка / Блок	Локти прижаты к рёбрам. Разгибайте руки полностью вниз.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	triceps	\N	\N	\N
32	Жим гантелей узким хватом лёжа	arms	Гантели	Ладони друг к другу, локти вдоль корпуса. Безопасно для локтевых связок.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	triceps	\N	\N	\N
33	Скручивания на полу	core	Свой вес	Поясница прижата, скручивайте грудной отдел к тазу на выдохе.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	abs	\N	\N	\N
34	Планка на предплечьях	core	Свой вес	Тело в одну прямую линию, пресс напряжён, поясница не проваливается.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	abs	\N	\N	\N
35	Подъём ног/коленей в висе на перекладине	core	Турник	Подкручивайте таз вверх на выдохе без раскачки корпуса.	Избегайте рывков, инерции и перегруза суставов.	t	t	t	abs	\N	\N	\N
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, username, password_hash, created_at, full_name, gender, age, height_cm, weight_kg, goal, work_schedule, injury_notes, is_onboarded) FROM stdin;
1	Александр	$2b$12$CxxgRUaxIDvk35KYLB4tJeGD9M7o9xuIPcR6B2OsjtITZCKTczHKa	2026-11-13 05:41:06.003112	\N	\N	\N	\N	\N	recomp	2/2	\N	f
2	Супруга	$2b$12$K.R4ryF.XYtflBJaGbieku0mEP0w5pEpBPRINAq7tfq0B5eOOdicO	2026-11-13 05:41:06.003117	\N	\N	\N	\N	\N	recomp	2/2	\N	f
\.


--
-- Data for Name: workouts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.workouts (id, user_id, exercise_name, sets, reps, weight, created_at) FROM stdin;
2	1	Подтягивания на перекладине	5	16	68	2026-10-25 09:15:48
3	1	Приседания с гантелью	5	12	25	2026-10-26 09:23:57
4	1	Подтягивания с весом	5	12	10	2026-10-26 09:30:52
5	1	Отжимания на брусьях с весом	5	14	10.5	2026-10-26 09:36:21
6	1	Подтягивания на перекладине	5	16	77	2026-10-30 09:30:21
7	1	Махи гантелей в стороны	5	14	9.5	2026-10-30 09:31:57
8	1	Тяга штанги  в наклоне	5	16	32.5	2026-10-31 10:27:16
9	1	Разведение гантелей в стороны на скамье	5	16	15	2026-10-31 12:59:35
10	1	Отжимания от пола	5	20	67	2026-10-31 13:44:10
11	1	Отжимания от банкетки на трицепс ДВ	4	18	15	2026-10-31 17:05:52
12	1	Алмазные отжимания	4	12	67	2026-10-31 17:43:18
13	1	Выход на две	1	4	68	2026-11-02 20:55:18
14	1	Подтягивания широким хватом	4	14	67.52	2026-11-02 20:56:05
15	1	Подтягивания на перекладине	5	15	68	2026-11-03 20:50:36
16	1	Подтягивания широким хватом	2	10	68.25	2026-11-03 20:52:08
17	1	Махи гантелей в стороны	5	14	10	2026-11-04 07:52:38
18	1	Приседания с резинкой	2	30	\N	2026-11-04 10:52:17
19	1	Приседания с гантелью	2	12	25	2026-11-04 11:02:53
20	1	Приседания с гантелью	2	14	25	2026-11-04 11:05:46
21	1	Махи гантелей в стороны	2	14	8.5	2026-11-04 11:13:49
22	1	Махи гантелей в стороны	2	18	8.5	2026-11-04 11:16:19
23	1	Махи гантелей в наклоне по очередно	2	22	10	2026-11-04 11:25:58
24	1	Жим гантелей на скамье 75 градусов	3	12	15	2026-11-04 11:41:26
25	1	Махи гантелей в наклоне	2	14	8.5	2026-11-04 11:54:01
26	1	Махи гантелей в наклоне	1	20	10.5	2026-11-04 11:57:56
27	1	Махи гантелей в наклоне	2	23	10.5	2026-11-04 12:01:21
28	1	Пресс книжка	3	20	\N	2026-11-04 12:16:29
29	1	Пресс на наклонной скамье с доп весом	1	20	5	2026-11-04 12:29:36
30	1	Пресс на наклонной скамье с доп весом	1	25	5	2026-11-04 12:31:20
31	1	Пресс на наклонной скамье с доп весом	1	27	5	2026-11-04 12:31:55
32	1	Подъем штанги в наклоне	3	16	32.5	2026-11-05 12:05:07
33	1	Подъем штанги в наклоне	2	23	32.5	2026-11-05 12:05:27
34	1	Подъем гантелей в наклоне на скамье по очередно	3	14	20.5	2026-11-05 12:10:57
35	1	Подъем гантелей в наклоне на скамье по очередно	1	16	20.5	2026-11-05 12:11:36
36	1	Французский жим штанги скамья 70 градусов	4	12	21	2026-11-05 12:30:30
37	1	Отжимания от скамьи на трицепс с весом	2	16	18	2026-11-05 12:52:05
38	1	Отжимания от скамьи на трицепс с весом	2	20	18	2026-11-05 12:52:46
39	1	Французский жим с резиной из-за ног	2	20	\N	2026-11-05 12:55:26
40	1	Подтягивания на перекладине	5	15	67	2026-11-12 09:00:24.401457
41	1	Разминочный подход	1	8	67	2026-11-12 09:00:24.401457
42	1	Разминочный подход	1	8	67	2026-11-12 09:00:24.401457
43	1	Приседания с резинкой	2	30	67	2026-11-08 11:23:55
44	1	Приседания с гантелью	2	12	25	2026-11-08 11:24:23
45	1	Приседания с гантелью	2	14	25	2026-11-08 11:24:39
46	1	Подъем штанги на бицепс	4	14	31	2026-11-08 12:06:39
47	1	Молотки	1	14	15.5	2026-11-08 12:07:44
48	1	Млотки	1	12	15.5	2026-11-08 12:08:13
49	1	Молотки	2	16	15.5	2026-11-08 12:08:48
50	1	Резина молотки	1	25	\N	2026-11-08 13:03:37
51	1	Пресс "Книжка"	2	20	\N	2026-11-08 13:04:19
52	1	Пресс "Книжка"	1	24	\N	2026-11-08 13:04:41
53	1	Пресс на наклонной скамье	1	28	5	2026-11-08 13:05:28
54	1	Пресс на наклонной скамье с доп весом	1	17	10	2026-11-08 13:06:12
55	1	Пресс на наклонной скамье с доп весом	1	18	10	2026-11-08 13:06:38
56	1	Пресс на наклонной скамье с доп весом	1	30	5	2026-11-08 13:07:07
57	1	Пресс "Альпинист"	2	38	\N	2026-11-08 13:08:05
58	1	Махи гантелей в стороны	2	16	6	2026-11-09 12:58:40
59	1	Махи гантелей в стороны	1	14	8.5	2026-11-09 12:59:08
60	1	Махи гантелей в стороны	2	16	8.5	2026-11-09 13:00:43
61	1	Махи гантелей в стороны	1	14	10.5	2026-11-09 13:01:09
62	1	Поочередные махи одной рукой с упором	2	16	10.5	2026-11-09 13:02:59
63	1	Махи гантелей в наклоне	1	16	8.5	2026-11-09 13:04:10
64	1	Махи гантелей в наклоне	1	26	8.5	2026-11-09 13:04:42
65	1	Махи гантелей в наклоне	1	20	10.5	2026-11-09 13:05:02
66	1	Подъем штанги к подбородку	3	12	31	2026-11-09 13:06:34
67	1	Подъем резины к подбородку	1	30	\N	2026-11-09 13:07:21
68	1	Жим гателей на наклонной скамье 75*	3	14	15.5	2026-11-09 13:09:00
69	1	Жим гателей на наклонной скамье 75*	1	11	15.5	2026-11-09 13:10:28
70	1	Жим гантелей на наклонной скамье 35*	3	15	15.5	2026-11-09 13:11:48
71	1	Жим гантелей лежа	2	16	15.5	2026-11-09 13:12:40
72	1	Приседания с фитнес-резинкой	3	30	\N	2026-11-12 14:45:18.752655
73	1	Гоблет-приседания (гантель 25 кг перед грудью)	4	14	25	2026-11-12 14:45:18.752655
74	1	Скручивания «книжка»	3	20	\N	2026-11-12 14:45:18.752655
75	1	Подъёмы корпуса на наклонной скамье	3	20	10	2026-11-12 14:45:18.752655
76	1	Суперсет «Ножницы + подъёмы прямых ног лёжа»	2	38	\N	2026-11-12 14:45:18.752655
77	1	Кардио-финишер «Альпинист»	2	42	\N	2026-11-12 14:45:18.752655
78	1	Махи гантелей в стороны	4	16	8.5	2026-11-13 14:15:48
79	1	Поочередные махи одной рукой с упором	2	16	10.5	2026-11-13 14:16:25
80	1	Поочередные махи одной рукой с упором	1	18	10.5	2026-11-13 14:16:49
81	1	Поочередные махи одной рукой с упором	1	24	8	2026-11-13 14:17:20
82	1	Жим гантелей сидя на наклонной скамье 35*	2	14	15.5	2026-11-13 14:18:12
83	1	Жим гантелей сидя на наклонной скамье 35*	1	15	15.5	2026-11-13 14:18:31
84	1	Жим гантелей сидя на наклонной скамье 35*	1	12	15.5	2026-11-13 14:18:48
85	1	Махи гантелей в наклоне	3	16	8	2026-11-13 14:19:44
86	1	Махи гантелей в наклоне	1	18	10.5	2026-11-13 14:20:05
87	1	Протяжка штанги до центра груди	3	12	31	2026-11-13 14:21:08
88	1	Протяжка штанги до центра груди	1	14	31	2026-11-13 14:21:34
89	1	Протяжка резинки до центра груди	1	28	\N	2026-11-13 14:22:22
\.


--
-- Name: exercises_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.exercises_id_seq', 35, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 1, false);


--
-- Name: workouts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.workouts_id_seq', 89, true);


--
-- Name: exercises exercises_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.exercises
    ADD CONSTRAINT exercises_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: workouts workouts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workouts
    ADD CONSTRAINT workouts_pkey PRIMARY KEY (id);


--
-- Name: ix_exercises_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_exercises_id ON public.exercises USING btree (id);


--
-- Name: ix_exercises_muscle_group; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_exercises_muscle_group ON public.exercises USING btree (muscle_group);


--
-- Name: ix_exercises_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_exercises_name ON public.exercises USING btree (name);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: ix_workouts_exercise_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_workouts_exercise_name ON public.workouts USING btree (exercise_name);


--
-- Name: ix_workouts_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_workouts_id ON public.workouts USING btree (id);


--
-- Name: ix_workouts_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_workouts_user_id ON public.workouts USING btree (user_id);


--
-- Name: workouts workouts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workouts
    ADD CONSTRAINT workouts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict tCFAnIbcSY9oF57tBi57YDSLIU63G1nEi7y7Lywqwk4WmhInvBUzbHIEIciTuNw

