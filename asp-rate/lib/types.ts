export type Task = {
  task_id: string;
  exam_type: "MI" | "ZI";
  exam_date: string;
  task_no: number;
  pdf_page: number;
  image_path: string;
  text_preview: string;
  cluster_id: number | null;
  cluster_label: string | null;
};

export type TasksManifest = {
  tasks: Task[];
};

export type TimeEstMinutes = 15 | 30 | 45 | 60;

export type Rating = {
  task_id: string;
  rater_uuid: string;
  difficulty: 1 | 2 | 3 | 4 | 5;
  time_est_minutes: TimeEstMinutes | null;
};
