export type Task = {
  task_id: string;
  exam_type: "MI" | "ZI";
  exam_date: string;
  task_no: number;
  pdf_page: number;
  image_path: string;
  text_preview: string;
};

export type TasksManifest = {
  tasks: Task[];
};

export type Rating = {
  task_id: string;
  rater_uuid: string;
  difficulty: 1 | 2 | 3 | 4 | 5;
};
