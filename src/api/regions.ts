import type { Department, Region } from "../types";
import { request } from "./http";

type RegionResponse = {
  id: string;
  code: string;
  name: string;
  order_index: number;
  departments: DepartmentResponse[];
};

type DepartmentResponse = {
  id: string;
  code: string;
  name: string;
  order_index: number;
  region_id: string;
};

const mapDepartment = (department: DepartmentResponse): Department => ({
  id: department.id,
  code: department.code,
  name: department.name,
  orderIndex: department.order_index,
  regionId: department.region_id,
});

const mapRegion = (region: RegionResponse): Region => ({
  id: region.id,
  code: region.code,
  name: region.name,
  orderIndex: region.order_index,
  departments: (region.departments || []).map(mapDepartment),
});

export const regionsApi = {
  list: async (): Promise<Region[]> => {
    const response = await request<RegionResponse[]>("/admin/regions");
    return response.data.map(mapRegion);
  },
};
