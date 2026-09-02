import { MockDengueRepository } from "./dengue.mock.repository";
import type { DengueRepository } from "./dengue.repository";

/** Punto único de inyección: cambiar aquí por HttpDengueRepository. */
export const dengueRepository: DengueRepository = new MockDengueRepository();

export type { DengueRepository };
