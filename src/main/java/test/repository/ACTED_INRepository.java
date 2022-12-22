package test.repository;


import org.springframework.data.neo4j.annotation.Query;
import org.springframework.data.neo4j.repository.Neo4jRepository;
import org.springframework.stereotype.Repository;
import test.domain.PO.ACTED_IN;

import java.util.List;

/**
 * 关系查询repo
 * 查询关系必须连带关系的两端节点也查出来
 * 所以关系实体必须用@StartNode和@EndNode修饰两端节点
 * 才能查出数据
 *
 * 所以每一个关系都要有自己的repo才行，即使属性相同名字不同也不能共用
 */
@Repository
public interface ACTED_INRepository extends Neo4jRepository<ACTED_IN,Long> {

    // 只支持一对一的关系
    @Query("match (n:Person{name:$personName}) -[m]-> (movie:Movie{title:$movieName}) return n,m,movie")
    List<ACTED_IN> findByNames(String personName, String movieName);
}