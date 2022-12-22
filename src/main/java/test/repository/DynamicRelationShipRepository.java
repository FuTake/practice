package test.repository;

import org.springframework.data.neo4j.annotation.Query;
import org.springframework.data.neo4j.repository.Neo4jRepository;
import test.domain.PO.DynamicRelationShip;
import test.domain.PO.Movie;
import test.domain.PO.Person;

import java.util.List;

public interface DynamicRelationShipRepository extends Neo4jRepository<DynamicRelationShip, Long> {

    // 动态neo4j无效
    @Query("match (n:Person{name:$personName}) -[m:ACTED_IN]- (movie:Movie{title:$movieName}) return n, m, movie")
    List<DynamicRelationShip<Person, Movie>> findByNames(String personName, String movieName);
}
