import type { Region } from "../types";
import { request } from "./http";

type RegionResponse = {
  id: string;
  code: string;
  name: string;
  order_index: number;
};

const mapRegion = (region: RegionResponse): Region => ({
  id: region.id,
  code: region.code,
  name: region.name,
  orderIndex: region.order_index,
});

export const regionsApi = {
  list: async (): Promise<Region[]> => {
    const response = await request<RegionResponse[]>("/admin/regions");
    return response.data.map(mapRegion);
  },
};
